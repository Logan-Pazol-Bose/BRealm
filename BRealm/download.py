import urllib2
import zipfile
import math
import os
import shutil

class HttpFile(object):
    def __init__(self, url):
        self.url = url
        self.offset = 0
        self._size = -1
        self._o = -1

    def size(self):
        if self._size < 0:
            f = urllib2.urlopen(self.url)
            self._size = int(f.headers["Content-length"])
        return self._size

    def readRange(self, start, end):
        req = urllib2.Request(self.url)
        req.headers['Range'] = "bytes=%s-%s" % (start, end)
        self._f = urllib2.urlopen(req).read()
        self._o = start
        self._len = end - start

    def read(self, count=-1):
        
        if count < 0:
            end = self.size() - 1
        else:
            end = self.offset + count - 1
        
        data = ""
        if self._o > 0:
            if self._o <= self.offset and self._o + self._len >= end:
                start = self.offset - self._o
                data = self._f[start: start + count]
        else:
            req = urllib2.Request(self.url)
            req.headers['Range'] = "bytes=%s-%s" % (self.offset, end)
            f = urllib2.urlopen(req)
            data = f.read()

        # FIXME: should check that we got the range expected, etc.
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


http = HttpFile("https://github.com/realm/realm-cocoa/releases/download/v3.7.2/Carthage.framework.zip")

print("Downloading zip dir")
f = zipfile.ZipFile(http)

minOffset = float('inf')
endOffset = -1

for name in f.namelist():
    
    info   = f.getinfo(name)
    offset = info.header_offset
    size   = info.compress_size
    comment = info.comment
    
    if "iOS" in name and not "dSYM" in name:
       
        minOffset = min(minOffset, offset)
        endOffset = max(endOffset, offset + size + 30 + len(name) + len(comment) + 13)

print("Downloading required contents")
http.readRange(minOffset, endOffset + 2)

print("Extracting")
for name in f.namelist():
    if "iOS" in name and not "dSYM" in name:
        print(name)
        f.extract(name)

shutil.rmtree("Realm.framework")
shutil.rmtree("RealmSwift.framework")

os.rename("Carthage/Build/iOS/Realm.framework", "Realm.framework")
os.rename("Carthage/Build/iOS/RealmSwift.framework", "RealmSwift.framework")
