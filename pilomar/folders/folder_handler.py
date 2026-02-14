"""Folder handling utilities for Pilomar telescope system.

Provides classes for managing folder structures for observation
sessions, campaigns, and image storage.

Copyright: GNU General Public License v3.0
"""

import os
import glob
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from pilomar.core.base import AttributeMaster


class FolderHandler(AttributeMaster):
    """Manages folder structures for Pilomar image storage.
    
    Creates and manages hierarchical folder structures for campaigns
    and observation sessions. Tracks folder existence and creates
    them on demand.
    
    Folder Structure:
        imageroot/
            campaign_{name}_{exposure}/
                session_{timestamp}/
                    dark/
                    light/
                    flat/
                    darkflat/
                    bias/
                    preview/
                    tracking/
                    
    Usage:
        handler = FolderHandler(projectroot='/home/pi/pilomar', logger=log)
        handler.new_session(campaign='mars', session='session_20240101120000')
        filename = handler.prep_file('light', 'image.jpg')
        
    Attributes:
        project_root: Base path for all folders.
        image_root: Root path for image storage.
        data_root: Root path for data files.
        folder_list: Dictionary of folder paths and existence status.
    """
    
    def __init__(
        self,
        projectroot: str,
        logger=None,
        os_command=None,
        usb_monitor=None,
        use_usb_storage: bool = False
    ):
        """Initialize folder handler.
        
        Args:
            projectroot: Base path for all project folders.
            logger: LogFile instance for logging.
            os_command: OsCommand instance for shell commands.
            usb_monitor: Disk monitor for USB storage.
            use_usb_storage: Whether to use USB for image storage.
            
        Raises:
            Exception: If projectroot doesn't exist.
        """
        self.set_logger(logger)
        
        if not Path(projectroot).exists():
            raise Exception(f"FolderHandler.__init__({projectroot}) does not exist.")
            
        self._os_command = os_command
        self.error_window = None
        self.folder_list = {}
        self.project_root = projectroot
        
        # Determine image storage location
        if use_usb_storage and usb_monitor and usb_monitor.drive_available:
            self.image_root = usb_monitor.df_path
            self.log(f"FolderHandler: Using USB storage at {self.image_root}", terminal=False)
        else:
            self.image_root = self.join_path(projectroot, 'data')
            self.log(f"FolderHandler: Using local storage at {self.image_root}", terminal=False)
            
        self.data_root = self.join_path(projectroot, 'data')
        
        # Create default session
        self.new_session(campaign='campaign', session='session')

    def list_campaign_folders(self) -> List[str]:
        """Return list of campaign folders on disc.
        
        Returns:
            List of absolute paths to campaign folders.
        """
        rootpath = self.get_path('imageroot') + "/campaign_*"
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def list_session_folders(self) -> List[str]:
        """Return list of session folders on disc.
        
        Returns:
            List of absolute paths to session folders.
        """
        rootpath = self.get_path('imageroot') + "/campaign_*/session_*"
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def list_image_folders(self, imagetype: str = 'light') -> List[str]:
        """Return list of image folders on disc.
        
        Args:
            imagetype: Type of image folder ('light', 'dark', etc.).
            
        Returns:
            List of absolute paths to image folders.
        """
        rootpath = self.get_path('imageroot') + f"/campaign_*/session_*/{imagetype}"
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def join_path(self, patha: str, pathb: str) -> str:
        """Join two path elements in OS-compatible way.
        
        Args:
            patha: First path element.
            pathb: Second path element.
            
        Returns:
            Joined path as string.
        """
        patha = self._to_path_type(patha)
        pathb = self._to_path_type(pathb)
        return str(Path.joinpath(patha, pathb))

    def valid_key(self, key: str) -> bool:
        """Check if a folder key is recognized.
        
        Args:
            key: Folder key to check.
            
        Returns:
            True if key exists in folder_list.
        """
        return key in self.folder_list
        
    def prep_file(self, key: str, filename: str) -> str:
        """Prepare full path for a file and ensure folder exists.
        
        Args:
            key: Folder key ('light', 'dark', etc.).
            filename: Name of file to create.
            
        Returns:
            Full path to the file.
        """
        fullpath = self.join_path(self.get_path(key), filename)
        self.create_folder_from_list_entry(key)
        return fullpath
        
    def new_session(self, campaign: str, session: str):
        """Set up folder structure for new campaign and session.
        
        Creates the standard folder hierarchy for a new observation session.
        Folders are not created immediately - they're made on demand.
        
        Args:
            campaign: Campaign name/identifier.
            session: Session name/identifier.
        """
        self.folder_list = {}
        campaign = self.clean_filename(campaign).lower()
        session = self.clean_filename(session).lower()
        
        self._add_project_folder(key="imageroot", foldername=self.image_root)
        self._add_project_folder(key="dataroot", foldername=self.data_root)
        self._add_project_folder(key="log", foldername=self.join_path(self.project_root, 'log'))
        self._add_project_folder(key="campaign", foldername=self.join_path(self.image_root, campaign))
        self._add_project_folder(key="temp", foldername=self.join_path(self.project_root, 'temp'))
        self._add_project_folder(key="session", foldername=self.join_path(self.get_path('campaign'), session))
        self._add_project_folder(key="tracking", foldername=self.join_path(self.get_path('session'), 'tracking'))
        self._add_project_folder(key="photometry", foldername=self.join_path(self.get_path('session'), 'photometry'))
        self._add_project_folder(key="auto", foldername=self.join_path(self.get_path('session'), 'auto'))
        self._add_project_folder(key="dark", foldername=self.join_path(self.get_path('session'), 'dark'))
        self._add_project_folder(key="darkflat", foldername=self.join_path(self.get_path('session'), 'darkflat'))
        self._add_project_folder(key="light", foldername=self.join_path(self.get_path('session'), 'light'))
        self._add_project_folder(key="flat", foldername=self.join_path(self.get_path('session'), 'flat'))
        self._add_project_folder(key="bias", foldername=self.join_path(self.get_path('session'), 'bias'))
        self._add_project_folder(key="preview", foldername=self.join_path(self.get_path('session'), 'preview'))
        
    def print_folder_list(self):
        """Print current folder list to terminal."""
        print("Current folder structure")
        for key, value in self.folder_list.items():
            exists_str = "exists " if value['exists'] else "       "
            print(f"- {key:10} {exists_str} {value['path']}")

    def _to_path_type(self, filepath) -> Path:
        """Ensure filepath is a Path object.
        
        Args:
            filepath: String or Path to convert.
            
        Returns:
            Path object.
        """
        if not isinstance(filepath, Path):
            filepath = Path(filepath)
        return filepath

    def file_age(self, filename: str):
        """Get age of file as timedelta.
        
        Args:
            filename: Path to file.
            
        Returns:
            Timedelta since modification, or None if file doesn't exist.
        """
        from datetime import datetime, timedelta
        if self.is_file(filename):
            mtime = os.path.getmtime(filename)
            return datetime.utcnow() - datetime.fromtimestamp(mtime)
        return None 
            
    def file_expired(self, filename: str, days: int = 0, hours: int = 0, 
                     minutes: int = 0, seconds: int = 0) -> bool:
        """Check if file is older than threshold.
        
        Args:
            filename: Path to file.
            days: Days threshold.
            hours: Hours threshold.
            minutes: Minutes threshold.
            seconds: Seconds threshold.
            
        Returns:
            True if file is older than threshold.
        """
        from datetime import timedelta
        age = self.file_age(filename)
        if age is None:
            return True
        threshold = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        return age >= threshold

    def get_path(self, key: str) -> Optional[str]:
        """Get folder path for a key.
        
        Args:
            key: Folder key ('light', 'dark', etc.).
            
        Returns:
            Folder path string, or None if key not found.
        """
        if key in self.folder_list:
            return self.folder_list[key].get("path", None)
        else:
            self.log(f"FolderHandler.get_path({key}) key not recognised", level='error')
            return None
        
    def _add_project_folder(self, key: str, foldername: str):
        """Add folder entry to folder_list.
        
        Args:
            key: Folder key.
            foldername: Folder path.
        """
        foldername = self.clean_filename(foldername)
        foldername = self._to_path_type(foldername)
        folderpath = self.join_path(self.project_root, foldername)
        entry = {
            'path': str(folderpath),
            'exists': self.path_exists(folderpath)
        }
        self.folder_list[key] = entry
        
    def clean_filename(self, filename: str) -> str:
        """Remove dangerous characters from filename.
        
        Args:
            filename: Path/filename to clean.
            
        Returns:
            Cleaned filename string.
        """
        filename = filename.replace(" ", "").replace("-", "").replace(":", "")
        filename = filename.replace("(", "").replace(")", "")        
        return filename

    def path_exists(self, folderpath) -> bool:
        """Check if path exists.
        
        Args:
            folderpath: Path to check.
            
        Returns:
            True if path exists.
        """
        folderpath = self._to_path_type(folderpath)
        return folderpath.exists()
        
    def name_only(self, folderpath) -> str:
        """Get filename without path.
        
        Args:
            folderpath: Full path.
            
        Returns:
            Filename component only.
        """
        folderpath = self._to_path_type(folderpath)
        return folderpath.name

    def is_file(self, folderpath) -> bool:
        """Check if path points to a file.
        
        Args:
            folderpath: Path to check.
            
        Returns:
            True if path is a file.
        """
        folderpath = self._to_path_type(folderpath)
        return folderpath.is_file()

    def get_parent(self, folderpath) -> Path:
        """Get parent directory of path.
        
        Args:
            folderpath: Path to check.
            
        Returns:
            Parent path.
        """
        folderpath = self._to_path_type(folderpath)
        return folderpath.parent

    def is_dir(self, folderpath) -> bool:
        """Check if path points to a directory.
        
        Args:
            folderpath: Path to check.
            
        Returns:
            True if path is a directory.
        """
        folderpath = self._to_path_type(folderpath)
        return folderpath.is_dir()
        
    def is_type(self, filepath, filetype, casesensitive: bool = False) -> bool:
        """Check if file matches a type (extension).
        
        Args:
            filepath: Path to check.
            filetype: Extension or list of extensions.
            casesensitive: Whether to match case.
            
        Returns:
            True if file type matches.
        """
        if isinstance(filetype, str):
            filetype = [filetype]
        filepath = self._to_path_type(filepath)
        foundtype = filepath.suffix.replace('.', '')
        
        if casesensitive:
            return foundtype in filetype
        else:
            filetype = [ft.lower() for ft in filetype]
            return foundtype.lower() in filetype

    def create_folder_from_list_entry(self, key: str):
        """Create folder for a known key if it doesn't exist.
        
        Args:
            key: Folder key.
        """
        if key in self.folder_list:
            if not self.folder_list[key]['exists']:
                folderpath = self.get_path(key)
                self.create_folder_by_path(folderpath)
                self.folder_list[key]['exists'] = True
                self.log(f"FolderHandler.create_folder_from_list_entry({key}) created: {folderpath}", 
                        terminal=False)
        else:
            self.log(f"FolderHandler.create_folder_from_list_entry({key}) key doesn't exist", 
                    terminal=False)

    def create_folder_by_path(self, folderpath):
        """Create folder and parent directories.
        
        Args:
            folderpath: Path to create.
        """
        try:
            self.log(f"FolderHandler.create_folder_by_path({folderpath})", terminal=False)
            folderpath = self._to_path_type(folderpath)
            if folderpath.is_file():
                folderpath = folderpath.parent
            folderpath.mkdir(mode=0o777, parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"FolderHandler.create_folder_by_path error: {e}", level='error')
    
    # Legacy method aliases (PascalCase)
    def ListCampaignFolders(self):
        return self.list_campaign_folders()
    
    def ListSessionFolders(self):
        return self.list_session_folders()
    
    def ListImageFolders(self, imagetype='light'):
        return self.list_image_folders(imagetype)
    
    def JoinPath(self, patha, pathb):
        return self.join_path(patha, pathb)
    
    def ValidKey(self, key):
        return self.valid_key(key)
    
    def PrepFile(self, key, filename):
        return self.prep_file(key, filename)
    
    def NewSession(self, campaign, session):
        return self.new_session(campaign, session)
    
    def PrintFolderList(self):
        return self.print_folder_list()
    
    def ToPathType(self, filepath):
        return self._to_path_type(filepath)
    
    def FileAge(self, filename):
        return self.file_age(filename)
    
    def FileExpired(self, filename, **kwargs):
        return self.file_expired(filename, **kwargs)
    
    def GetPath(self, key):
        return self.get_path(key)
    
    def AddProjectFolder(self, key, foldername):
        return self._add_project_folder(key, foldername)
    
    def CleanFilename(self, filename):
        return self.clean_filename(filename)
    
    def PathExists(self, folderpath):
        return self.path_exists(folderpath)
    
    def NameOnly(self, folderpath):
        return self.name_only(folderpath)
    
    def IsFile(self, folderpath):
        return self.is_file(folderpath)
    
    def GetParent(self, folderpath):
        return self.get_parent(folderpath)
    
    def IsDir(self, folderpath):
        return self.is_dir(folderpath)
    
    def IsType(self, filepath, filetype, casesensitive=False):
        return self.is_type(filepath, filetype, casesensitive)
    
    def CreateFolderFromListEntry(self, key):
        return self.create_folder_from_list_entry(key)
    
    def CreateFolderByPath(self, folderpath):
        return self.create_folder_by_path(folderpath)
    
    # Legacy attribute aliases
    @property
    def ProjectRoot(self):
        return self.project_root
    
    @property
    def ImageRoot(self):
        return self.image_root
    
    @property
    def DataRoot(self):
        return self.data_root
    
    @property
    def FolderList(self):
        return self.folder_list
    
    @property
    def ErrorWindow(self):
        return self.error_window
    
    @ErrorWindow.setter
    def ErrorWindow(self, value):
        self.error_window = value


# Backward compatibility alias
folderhandler = FolderHandler
