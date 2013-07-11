from musicmover import MusicMover

import time
import Tkinter as tk
import ttk
import tkMessageBox, tkFileDialog


class TkMusicMover(MusicMover):
    """ A version of MusicMover with a minimal UI.
    """

    def _closeWindowHandler(self):
        if tkMessageBox.askokcancel("Quit", "Do you really wish to cancel?"):
            self.canceled = True


    def _createUi(self):
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", self._closeWindowHandler)
        dialogWidth = max(self.root.winfo_screenwidth() * .8, 1024)
        self.root.title("MusicMover")

        frame = tk.Frame(self.root)
        self.label1 = ttk.Label(frame, text="")
        self.label2 = ttk.Label(frame, text="")
        self.pb = ttk.Progressbar(frame, length=dialogWidth)
        self.label1.pack(fill=tk.X, anchor="w")
        self.label2.pack(fill=tk.X, anchor="w")
        self.pb.pack(anchor='sw')
        frame.pack(side=tk.TOP)


    def _destroyUi(self):
        self.root.destroy()


    def deleteCallback(*args, **kwargs):
        # Just suppress the printing done by the default version.
        pass


    def copyCallback(self, num, total, orig, dupe):
        """ Called after each track is duplicated.
        """
        self.label1.config(text="Copying file %d of %d:" % (num, total))
        self.label2.config(text=dupe)
        self.label1.update()
        self.label2.update()
        self.pb.step()
        self.pb.update()


    def copyTracks(self, tracks, dest=None):
        """ Copy iTunes tracks, updating the GUI.
        """
        self.pb.config(maximum=len(tracks))
        return MusicMover.copyTracks(self, tracks, dest)


    def freshenMusic(self, **kwargs):
        """ Called before tracks are copied. Prompts the user to select a
            target directory if none was supplied to ``__init__()``.
        """
        self._createUi()
        if not self.target:
            self.target = tkFileDialog.askdirectory(parent=self.root,
                initialdir="/Volumes/", title='Please select a directory')
        if self.target != '':
            # Should only occur if the directory chooser was cancelled.
            MusicMover.freshenMusic(self, **kwargs)
        self._destroyUi()


#===============================================================================
# 
#===============================================================================

if __name__ == "__main__":
    pass
