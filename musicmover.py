"""
A tool for copying music in iTunes to another device. Intended primarily for
loading music onto a non-Apple device (e.g. an Android-based smartphone), 
mounted as a USB drive.

Requires Python 2.6/7 and MacOS X.

@todo: Revisit were I use 'yield' vs. returning lists. Make sure there aren't
    any places that could spend the generator unexpectedly.
@todo: Consider removing target directory from method arguments, using only
    the target specified when the MusicMover object was created.
@todo: See about burning DVD-R from Python, for use with MusicMover.partition().
    Can probably be done with osascript, albeit slowly.
"""

import os
import plistlib
import random
import shutil
from urllib import url2pathname, unquote
from urlparse import urlparse

#===============================================================================
# 
#===============================================================================

class iTunesLibrary(object):
    """ A class wrapping the iTunes Library XML data. Abstracted for possibly
        implementing as a real database or something more directly in
        communication with iTunes.
    """
    
    def __init__(self, library="~/Music/iTunes/iTunes Music Library.xml"):
        self.filename = os.path.realpath(os.path.expanduser(library))
        self.libdata = plistlib.readPlist(self.filename)
        self.playlists = {}
        for pl in self.libdata['Playlists']:
            self.playlists[pl['Name']] = pl


    def __repr__(self):
        return "<iTunes Library: %r>" % self.filename


    def getPlaylists(self):
        """ Get a list of playlist names.
        
            @return: A list of playlist names (strings).
        """
        return self.playlists.keys()


    def getPlaylistIds(self, name):
        """ Retrieve a list of all track IDs within a given playlist.
        
        """
        playlist = self.playlists[name]
        for p in playlist['Playlist Items']:
            i = p.get('Track ID')
            if i is not None:
                yield i
    

    def getTrackById(self, trackId):
        """ Get a single track by its ID.
        
            @param trackId: The ID of the given track. 
            @return: The given Track, a dict-like object.
        """
        return self.libdata['Tracks'].get(str(trackId))
    

    def getTracks(self, playlist="Music", filterFunc=None):
        """ Get all tracks in a given playlist.
        
            @keyword playlist: The name of the playlist from which to get the
                tracks. Defaults to "Music" (all music in the library).
            @keyword filterFunc: A function to exclude certain tracks. Applied
                to each 'track' dict.
            @return: A generator of Tracks (dict-like objects).
        """
        if filterFunc is None:
            filterFunc = lambda(x): True
        for i in self.getPlaylistIds(playlist):
            t = self.getTrackById(i)
            if t is not None and filterFunc(t):
                yield t


#===============================================================================
# 
#===============================================================================

class MusicMover(object):
    """ A class for copying iTunes files to another device, plus (optionally)
        removing some portion of the music files on the target device to
        'freshen' its contents.
        
        @ivar canceled: If this becomes `True` before an action is completed
            (``freshenMusic()``, ``copyTracks()``), the action stops.
        @cvar musicExt: The filename extensions of valid music files.
        @cvar minFreeSpace: The default amount of free space to leave when
            freshening music (MB).
    """

    musicExt = [".mp3", ".aiff", ".m4a", ".aac", ".wav", ".ogg"]
    minFreeSpace = 100

    badCharacters = """/~\\"':;<>\x7f\n*"""

    def __init__(self, libraryFile="~/Music/iTunes/iTunes Music Library.xml",
                 target=None, library=None):
        """ Constructor.
            @keyword libraryFile: The path and name of the iTunes music library
                XML file.
            @keyword target: The destination directory to which to copy music.
            @keyword library: An `iTunesLibrary` object, as a convenience to
                prevent having to parse the XML unnecessarily.
        """
        if library is None:
            library = iTunesLibrary(libraryFile)
        self.library = library
        self.target = target
        self.canceled = False


    def _sanitize(self, filename, target):
        """ Clean a filename so that it is compatible with the target
            filesystem.
        """
        # TODO: Should probably do this based on character code.
        name, ext = os.path.splitext(filename)
        for c in self.badCharacters:
            name = name.replace(c, '_')
        return name + ext
        

    def targetName(self, track, target=None):
        """ Get the path and name to which a file will be copied, performing
            any sort of conversion of the name required by the target
            filesystem.
        """
        target = self.target if target is None else target
        trackName = os.path.basename(unquote(urlparse(track.get('Location', '')).path))
        album = self._sanitize(track.get('Album', 'Unknown Album'), target)
        if track.get('Compilation', False):
            artist = "Compilations"
        else:
            artist = self._sanitize(track.get('Artist', 'Unknown Artist'),
                                    target)
        
        return os.path.abspath(os.path.join(target, artist, album, trackName))


    def canBeDeleted(self, f):
        """ Determine if a file can be deleted.
        """
        return True


    def isMusicFile(self, f):
        """ Function to filter out non-music files. Checks only the filename.
        """
        if f.startswith('.'):
            return False
        ext = os.path.splitext(f)[-1].lower()
        return ext in self.musicExt


    def getStats(self, drive):
        """ Return (free space, block size) for a given drive. Replace if
            the target device isn't really a normal filesystem. Note that the
            path must exist.

            @param drive: The path of the drive to check (e.g.
                /Volumes/MYDRIVE/)
            @return: A tuple containing (<bytes free>, <block size>)
        """
        s = os.statvfs(drive)
        return (s.f_frsize * s.f_bavail, s.f_frsize)


    def roundUpTo(self, num, blocksize):
        """ Get the size of a file (plus padding) rounded up to a given block
            size.
        """
        d = num / blocksize
        if num % blocksize > 0:
            d += 1
        return int(blocksize * d + .5)


    def getMusicFiles(self, path=None):
        """ Recursively get all music files from a given path.
        
            @keyword path: The destination path. Defaults to the 'target'
                specified when constructing the MusicMover object.
        """
        path = self.target if path is None else path
        for root, dirs, files in os.walk(path):
            files = filter(self.isMusicFile, files)
            for name in files:
                yield os.path.join(root, name)


    def getMusicSize(self, files, roundUp=True):
        """ Calculate the size of a set of files.
        """
        files = list(files)
        if len(files) == 0:
            return 0
        if roundUp:
            blocksize = self.getStats(files[0])[1]
            return sum(map(lambda x: self.roundUpTo(os.path.getsize(x), 
                                                    blocksize), files))
        return sum(map(os.path.getsize, files))
        

    def getRemovalList(self, path=None, percent=33, filterFunc=canBeDeleted,
                       files=None):
        """ Get a list of music files to remove, based on a percentage of all
            music files in a given directory.

            @param path: The root directory from which to get the files.
            @keyword percent: The percentage (0-100) of filenames to return.
            @keyword filterFunc: A function that determines whether a given
                file is eligible for deletion.
            @keyword files: A list of files from which to do the removal. If
                none is supplied, it defaults to all music files in the
                specified path.
        """
        path = self.target if path is None else path
        if files is None:
	       files = filter(filterFunc, self.getMusicFiles(path))
        else:
            files = list(files)
        random.shuffle(files)
        idx = int(len(files) * percent * 0.01 + 0.5)
        toDelete = files[:idx]
        toDelete.sort()
        return toDelete


    def getNewMusic(self, dest=None, maxSize=None, minFree=minFreeSpace,
                    playlist="Music", oldFiles=None, filterFunc=None):
        """ Create a list of files to copy to the target drive.

            @keyword dest: The destination path. Defaults to the 'target'
                specified when constructing the MusicMover object.
            @keyword maxSize: The maximum amount of data (in MB) to copy to the
                destination drive. Takes precedence over `minFree`.
            @keyword minFree: The minimum number of megabytes to leave free on
                the destination drive.
            @keyword playlist: The name of the iTunes playlist from which to
                copy. Defaults to "Music", which is all music.
            @keyword oldFiles: A set of filenames (on the destination) to
                exclude from the set of new music; this is presumably a list
                of files that were on the drive prior to any deletion done to
                freshen the music. Defaults to the contents of the destination
                directory tree.
            @returns: (<total bytes to be copied>, [<track1>, <track2>, ...]) 
        """
        dest = self.target if dest is None else dest
        targetFree, targetBlockSize = self.getStats(dest)

        if minFree is None and maxSize is None:
            raise ValueError, "Either minFree or maxSize must be supplied."

        if maxSize is None:
            maxSize = self.round(bytesFree/1048576) - minFree
        
        maxSize = self.roundUpTo(maxSize * 1048576, targetBlockSize)
            

        total = 0
        tracks = []
        if oldFiles is None:
            existingFiles = self.getMusicFiles(dest)
        else:
            existingFiles = oldFiles
            
        # By default, iTunes mixes formats in it 'Music' playlist, so remove
        # non-music items explicitly.
        tracks = filter(lambda t: self.isMusicFile(t.get('Location','')),
                        self.library.getTracks(playlist, filterFunc=filterFunc))

        random.shuffle(tracks)
        newTracks = []
        for track in tracks:
            filesize = track.get('Size',-1)
            newTotal = total + self.roundUpTo(filesize, targetBlockSize)
            if newTotal >= maxSize:
                break
            copyName = self.targetName(track, dest)
            if copyName in existingFiles:
                continue
            newTracks.append(track)
            total = newTotal
        return (total, newTracks)


    def copyFile(self, source, dest):
        """ Copy a file, creating the destination subdirectory if required.
            Replace this for debugging purposes, or if the target device isn't
            really a normal filesystem.
        """
        destPath = os.path.dirname(dest)
        if not os.path.exists(destPath):
            os.makedirs(destPath)
            
        p = urlparse(source)
        scheme = p.scheme.lower()
        
        if scheme == "file":
            sourceFile = os.path.abspath(url2pathname(p.path))
            return shutil.copy2(sourceFile, dest)
        else:
            raise NotImplementedError("Unknown scheme for %r" % source)


    def copyCallback(self, num, total, orig, dupe):
        """ Called after every file is copied. This one is placeholder, and
            is meant to be replaced by something more interesting (GUI, etc.).
        """
        print "copying %d of %d: %s" % (num, total, dupe)


    def deleteFile(self, filename):
        """ Delete a file. Replace this for debugging purposes, or if the
            target device isn't really a normal filesystem.
        """
        return os.remove(filename)


    def deleteCallback(self, num, total, filename):
        """ Called after every file is deleted. This one is placeholder, and
            is meant to be replaced by something more interesting (GUI, etc.).
        """
        print "deleting %d of %d: %s" % (num, total, filename)
    

    def copyMusic(self, totalSize, files):
        """ Copy music files. Uses the ``copyFile`` method (to keep things 
            slightly abstract and flexible). 

            @param totalSize: The total number of bytes to be copied.
            @param sourceRoot: The common root directory of all music files.
            @param files: A list of filename tuples, (<original>,<duplicate>).
                The original filenames are relative to `sourceRoot`.
        """
        totalFiles = len(files)
        c = 1
        for original, dupe in files:
            if self.canceled:
                break
            self.copyCallback(c, totalFiles, original, dupe)
            self.copyFile(original, dupe)
            c+=1


    def preCopyTracks(self):
        """ Called before music files have been copied (by ``freshenMusic()``, 
            ``copyTracks()``, etc.), doing any preparation that may be required.
            This one is placeholder, and is meant to be replaced by something 
            more interesting (GUI, etc.).
        """
        pass


    def postCopyTracks(self):
        """ Called after music files have been copied (by ``freshenMusic()``, 
            ``copyTracks()``, etc.), doing any cleanup that may be required.
            This one is placeholder, and is meant to be replaced by something 
            more interesting (GUI, etc.).
        """
        pass


    def freshenMusic(self, dest=None, playlist="Music", percent=33,
                     maxSize=None, minFree=minFreeSpace,
                     deleteFilter=None, newFilter=None):
        """ Remove some portion of the music on the target device, then copy
            over new music. The amount of new material is determined by either
            a maximum size of copied material or by a minimum amount of free
            space to leave.
            
            @keyword dest: The destination path. Defaults to the 'target'
                specified when constructing the MusicMover object.
            @keyword maxSize: The maximum total size (in MB) of the freshened 
                music collection.
            @keyword minFree: The minimum number of megabytes to leave free on
                the destination drive.
            @keyword playlist: The name of the iTunes playlist from which to
                copy. Defaults to "Music", which is all music.
            @keyword oldFiles: A set of filenames (on the destination) to
                exclude from the set of new music; this is presumably a list
                of files that were on the drive prior to any deletion done to
                freshen the music. Defaults to the contents of the destination
                directory tree.
            @keyword deleteFilter: A function that determines if a given
                existing music file can be deleted. By default, any music file
                can be deleted.
            @keyword newFilter: A function that determines if a track can be 
                copied to the target. Defaults to any audio track.
        """
        
        dest = self.target if dest is None else dest
        oldFiles = list(self.getMusicFiles(dest))
        toDelete = self.getRemovalList(dest, percent=percent,
                                       filterFunc=deleteFilter, files=oldFiles)
        
        if maxSize is not None:
            maxSize -= self.getMusicSize(oldFiles) / 1048576
            
        totalToDelete = len(toDelete)
        for i in xrange(totalToDelete):
            if self.canceled:
                break
            f = toDelete.pop()
            self.deleteFile(f)
            self.deleteCallback(i, totalToDelete, f)
            
        
        m = self.getNewMusic(dest, maxSize, minFree, playlist,
                             oldFiles=oldFiles, filterFunc=newFilter)
        self.copyTracks(m[1], dest=dest)
        self.postCopyTracks()


    def partition(self, playlist="Music", maxSize=4300, dest=None,
                  blockSize=2048, useDestBlocksize=False, filterFunc=None):
        """ Produce a list of lists from the given playlist, each containing
            a specified amount of data. Intended for doing backups to DVD-R.
            
            @keyword playlist: The name of the iTunes playlist from which to
                copy. Defaults to "Music", which is all music.
            @keyword maxSize: The maximum amount of data (in MB) to copy to the
                destination drive. Takes precedence over `minFree`.
            @keyword dest: The destination path. Defaults to the 'target'
                specified when constructing the MusicMover object.
            @keyword blockSize: The block size on the target device. Defaults
                to 2048, a standard size for DVD-ROM.
            @returns: ``[[track, track, ...],[track, track, ...],..]``
        """
        dest = self.target if dest is None else dest

        targetFree, targetBlockSize = self.getStats(dest)
        if useDestBlocksize:
            blocksize = targetBlockSize
        maxSizeBytes = maxSize * 1024 * 1024

        total = 0
        allTracks = [[]]
        trackSet = allTracks[0]
        
        for track in self.library.getTracks(playlist, filterFunc=filterFunc):
            filesize = track.get('Size', 0)
            if filesize == 0:
                continue
            filesize = self.roundUpTo(filesize, blockSize)
            if filesize > maxSizeBytes:
                raise Exception("Track is larger than the partition size: %s" \
                                % filesize)
            newTotal = total + filesize
            if newTotal >= maxSizeBytes:
                trackSet = []
                allTracks.append(trackSet)
                newTotal = filesize
            trackSet.append(track)
            total = newTotal
            
        return allTracks


    def copyTracks(self, tracks, dest=None):
        """ Copy a set of tracks. Does not do any special handling, such as 
            checking free space, et cetera; standard exceptions will be raised
            if there's a problem along those lines.
        
            @param tracks: A list of Track objects.
            @keyword dest: The destination path. Defaults to the 'target'
                specified when constructing the MusicMover object.
        """
        dest = self.target if dest is None else dest
        totalFiles = len(tracks)
        c = 1
        self.preCopyTracks()
        for track in tracks:
            if self.canceled:
                break
            dupe = self.targetName(track, dest)
            self.copyFile(track['Location'], dupe)
            self.copyCallback(c, totalFiles, track, dupe)
            c+=1
        self.postCopyTracks()


#===============================================================================
# 
#===============================================================================

if __name__ == "__main__":
    from argparse import ArgumentParser
    from tk_musicmover import TkMusicMover

    parser = ArgumentParser(
        description="MusicMover: Copy music from iTunes to another device.")
    
    parser.add_argument("--library", "-l", 
        help="The iTunes library XML file to use.",
        default="~/Music/iTunes/iTunes Music Library.xml")
    parser.add_argument("--gui", "-g", action="store_true",
        help="Use the GUI version.")
    parser.add_argument("--minfree", "-f", type=int, default=None,
        help="The minimum amount of space (MB) to leave on the target device.")
    parser.add_argument("--maxsize", "-m", type=int, default=None,
        help="The maximum size (in MB) of the target's music directory.")
    parser.add_argument("--playlist", "-p", default="Music",
        help="The name of the iTunes playlist from which to copy.")
    parser.add_argument("--percent", "-t", type=int, default=33,
        help="The percentage of music to 'freshen' (delete and replace on " \
            "the device).")
    parser.add_argument("target", 
        help="The target root directory (e.g. /Volumes/PHONE/Music). "\
            "This directory must exist.")
    
    args = parser.parse_args()
   
    MM = MusicMover
    if args.gui:
        MM = TkMusicMover
    
    mover = MusicMover(libraryFile=args.library, target=args.target)
    
    mover.freshenMusic(playlist=args.playlist, percent=args.percent,
                       minFree=args.minfree, maxSize=args.maxsize)
    
