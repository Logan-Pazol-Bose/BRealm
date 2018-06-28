import urllib2
import zipfile
import shutil
import json
import math
import os

def MANIFEST():
    return "manifest.json"

def BASELOCALHEADERSIZE():
    return 30

def DATADESCRIPTORSIZE():
    return 12

class DataRequester(object):
    def __init__(self, url):
        self.url   = url
        self._size = -1
        self._resolved = ""

    def dataForRange(self, start, end):
        
        url = self.url
        if len(self._resolved) > 0:
            url = self._resolved
        
        request = urllib2.Request(url)
        request.headers['Range'] = "bytes=%s-%s" % (start, end)
        request.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) Gecko/20100101 Firefox/42.0'
        
        response = urllib2.urlopen(request)
        self._resolved = response.geturl()
        return response.read()

    def size(self):
        if self._size < 0:
            f = urllib2.urlopen(self.url)
            self._resolved = f.geturl()
            self._size = int(f.headers["Content-length"])
        return self._size


class DataBlock(object):
    def __init__(self):
        self.start = 0
        self.end   = 0
        self.data  = ""
    
    def load(self, dataRequester, start, end):
        self.start = start
        self.end   = end
        self.data  = dataRequester.dataForRange(start, end)
    
    def isRangeContainedInData(self, start, count):
        return start >= self.start and start + count <= self.end

    def dataForRange(self, start, count):
        newStart = start    - self.start
        newEnd   = newStart + count

        return self.data[newStart:newEnd]

class HttpFile(object):
    def __init__(self, url):
        self.dataRequester = DataRequester(url)
        self.offset = 0
        self.preloadedRange = DataBlock()

    def size(self):
        return self.dataRequester.size()

    def preloadRange(self, start, end):
        self.preloadedRange.load(self.dataRequester, start, end)
    
    def read(self, count=-1):
        
        if count < 0:
            end = self.size() - 1
        else:
            end = self.offset + count - 1
        
        data = ""
        if self.preloadedRange.isRangeContainedInData(self.offset, count):
            data = self.preloadedRange.dataForRange(self.offset, count)
        else:
            data = self.dataRequester.dataForRange(self.offset, end)

        chunk = len(data)
        if count >= 0:
            assert chunk == count

        self.offset += chunk
        return data

    def seek(self, offset, whence=0):
        if whence == 0:
            self.offset = offset
        elif whence == 1:
            self.offset += offset
        elif whence == 2:
            self.offset = self.size() + offset
        else:
            raise Exception("Invalid whence")

    def tell(self):
        return self.offset

def numberOfBytesForFile(fileInfo):
    size    = fileInfo.compress_size
    comment = fileInfo.comment
    name    = fileInfo.filename
    return size + BASELOCALHEADERSIZE() + len(name) + len(comment) + DATADESCRIPTORSIZE()

def loadZipRangeForItemsSatisfyingPred(zipFile, httpFile, pred):
    startOffset = float('inf')
    endOffset   = -1

    for name in zipFile.namelist():
        if pred(name):
            fileInfo = zipFile.getinfo(name)
            start    = fileInfo.header_offset
            end      = start + numberOfBytesForFile(fileInfo)
            
            startOffset = min(startOffset, start)
            endOffset   = max(endOffset,   end)

    # MAGIC!
    endOffset = endOffset + 2

    httpFile.preloadRange(startOffset, endOffset)

def extractFilesThatSatisfyPred(zipFile, pred):
    for name in zipFile.namelist():
        if pred(name):
            zipFile.extract(name)

def isMultiOS(zipFile):
    for name in zipFile.namelist():
        if "Carthage" in name:
            return True
    return False

def moveFrameworks(zipFile, pred, frameworks):
    for framework in frameworks:
        if os.path.isdir(framework):
            shutil.rmtree(framework)
    
    for name in zipFile.namelist():
        if pred(name):
            filename = os.path.basename(os.path.normpath(name))
            for framework in frameworks:
                if filename == framework:
                    print(name)
                    os.rename(name, framework)

def download(frameworks, githubRelease):
    httpFile = HttpFile(githubRelease)
    
    size = httpFile.size()
    httpFile.preloadRange(max(0, size - 8000), size - 1)
    
    print("Downloading zip dir")
    file = zipfile.ZipFile(httpFile)
    mutliOS = isMultiOS(file)
    
    def pred(filename):
        if (not mutliOS or "iOS" in filename) and not "dSYM" in filename:
            for framework in frameworks:
                if framework in filename:
                    return True
        return False
    
    print("Downloading block that satisfies predicate")
    loadZipRangeForItemsSatisfyingPred(file, httpFile, pred)
    
    print("Extracting files")
    extractFilesThatSatisfyPred(file, pred)

    moveFrameworks(file, pred, frameworks)

def linkToZip(manifest):
    if "release" in manifest:
        return manifest["release"]
    else:
        return releaseFromRepo(manifest["repo"], manifest["filenamePrefix"])

def releaseFromRepo(repo, prefix):
    response = urllib2.urlopen("https://api.github.com/repos/" + repo + "/releases/latest").read()
    parsed = json.loads(response)

    for asset in parsed["assets"]:
        if prefix in asset["name"]:
            return asset["browser_download_url"]
    return ""

#---------------------------------------------------------

manifest = json.loads(open(MANIFEST()).read())
frameworks = manifest["frameworks"]

needsDownload = False
for framework in frameworks:
    if not os.path.isdir(framework):
        needsDownload = True

if needsDownload:
    link = linkToZip(manifest)
    print("Downloading zip from: " + link)

    if len(frameworks) > 0:
        download(frameworks, link)

