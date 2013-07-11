musicmover
==========

A tool for copying iTunes tracks to a non-Apple device (e.g. an Android phone) under MacOS X. Beyond simply copying, this tool 'freshens' the music on the device; a percentage of the device's existing audio tracks (33% by default) are replaced by new ones from the iTunes library. 

Of course, freshening only works if the device only stores a subset of the music available. 128GB MicroSD in phones is an inevitability.

This was just a personal project that I thought might benefit others. There are no warranties, guarantees, or technical support plans. 

The main file, ``musicmover.py``, implements ``iTunesLibrary`` and ``MusicMover`` classes. The file ``tk_musicmover.py``, implements a subclass of ``MusicMover`` with a basic Tk interface.

usage
=====

The main ``musicmover.py`` script is executable, and provides standard CLI help messages. The best way to use the tool is to create a shell script (or executable Python) that calls ``musicmover.py`` with the appropriate arguments (the path to your specific device, mounted as a USB drive, et cetera).


todo
===

* Keep a history of music that's been on the phone, so a second freshening doesn't restore things that were previously on the device.
* Only remove files from the device that are in the iTunes library, to avoid deleting items copied manually from another source. 
* Burn backups of a library to DVD-R. ``MusicMover.partition()`` will split a playlist into appropriately-sized chunks, but nothing else. See about actually burning discs, possibly via osascript.
