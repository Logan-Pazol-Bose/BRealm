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

    def dataForRange(self, start, end):
        request = urllib2.Request(self.url)
        request.headers['Range'] = "bytes=%s-%s" % (start, end)

        return urllib2.urlopen(request).read()

    def size(self):
        if self._size < 0:
            f = urllib2.urlopen(self.url)
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

def download(frameworks, githubRelease):
    httpFile = HttpFile(githubRelease)
    
    def pred(filename):
        if "iOS" in filename and not "dSYM" in filename:
            for framework in frameworks:
                if framework in filename:
                    return True
        return False
    
    print("Downloading zip dir")
    file = zipfile.ZipFile(httpFile)
    
    print("Downloading block that satisfies predicate")
    loadZipRangeForItemsSatisfyingPred(file, httpFile, pred)
    
    print("Extracting files")
    extractFilesThatSatisfyPred(file, pred)
    
    for framework in frameworks:
        if os.path.isfile(framework):
            shutil.rmtree(framework)
        os.rename("Carthage/Build/iOS/" + framework, framework)

#---------------------------------------------------------

manifest = json.loads(open(MANIFEST()).read())
frameworks = manifest["frameworks"]

if len(toDownload) > 0:
    download(frameworks, manifest["release"])

