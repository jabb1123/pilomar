import glob
import os
from oscommand import OSCommand
from utils import AttributeMaster
from utils.params import Parameters
from utils.text.textcolor import TextColor


class FolderHandler(AttributeMaster):
    """Class to define folders for various images.
    This can also ensure that a folder exists when needed.

    Usage:

      FolderHandler = folderhandler(projectroot=ProjectRoot,logger=MainLog) # Create FolderHandler instance. Defines and create folder structures.
      FolderHandler.NewSession(campaign='mycampaign',session='mysession') # Define dummy structures until target chosen.
      filename = FolderHandler.PrepFile('light','image.jpg') # Return full path where a 'light' image is to be stored. This will also check that the structure exists.
      image.save(filename)

    "imageroot" = imageroot # Don't 'verify' the root structure. (For safety!) # Root of folders for campaign (image) data. If it's missing, it's an error.
    "dataroot" = dataroot # Don't 'verify' the root structure. (For safety!) # Root of folders for other data (target lists, parameters etc). If it's missing it's an error.
    "campaign" = imageroot + campaign # The parent folder for the campaign. Which could store work over several nights.
    "temp" = ProjectRoot + "temp" # Temporary folder for experiments.
    "session" = imageroot + session # The folder for an individual session.
    "tracking" = imageroot + session + "tracking" # This is the folder where tracking images are stored.
    "auto" = imageroot + session + "auto" # This is the folder where automatic images are stored (Normally during commissioning).
    "dark" = imageroot + session + "dark" # The Pi-lomar folder for the DARK images.
    "darkflat" = imageroot + session + "darkflat" # The folder for the DARK FLAT images.
    "light" = imageroot + session + "light" # The Pi-lomar folder for the LIGHT images. (The actual observations)
    "flat" = imageroot + session + "flat" # The Pi-lomar folder for the FLAT images.
    "bias" = imageroot + session + "bias" # The Pi-Lomar folder for the BIAS/OFFSET images.
    "preview" = imageroot + session + "preview" # The folder for the PREVIEW images.

    # O/S aware file/folder path operations :-
    from pathlib import Path
    folder = Path("/home/foldera/folderb") # Auto converts separators.
    filepath = Path.joinpath(folder,"filename.txt") # Appends the filename to the path automatically.
    filepath.parts returns ("/","home","foldera","folderb","filename.txt")
    filepath.root returns "/"
    filepath.parents returns list of parent structure, must use an index though! parents[1], parents[2], doesn't return entire list.
    filepath.parent returns immediate parent directory
    filepath.name = filename element
    filepath.suffix = filetype
    filepath.stem = filename without suffix
    Path.cwd() returns current working directory
    Path.home() returns user's home directory
    folder.chmod(...) change mode.
    filepath.exists() return True if file exists.
    filepath.is_dir()
    filepath.is_file()
    # filepath.walk(top_down=True) return tuple of structure. - Not in current RPi Python.
    filepath.mkdir(mode=0o777, parents=True, exist_ok=True) # Create directory and any required parents, don't complain if already exists.
    filepath.touch(mode=0o777, exist_ok=True) # Create / modify file.

    """

    def __init__(self, projectroot, logger=None):
        """Initialize the instance."""
        self.set_logger(
            logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        if not Path(projectroot).exists():  # Project root is missing.
            raise Exception(
                "folderhandler.__init__(" + str(projectroot) + ") does not exist."
            )
        self.oscommand = OSCommand(logger=logger.Log)  # Create OS command executor.
        self.os_cmd = (
            self.oscommand.execute
        )  # Point to the chosen Execute method for os commands.
        self.error_window = None  # Handle to optional error window.
        self.folder_list = {}  # Initial empty list of folders and attributes.
        self.project_root = projectroot  # The base of all folders. Only folders beneath this level are created/modified.
        if Parameters.use_usb_storage and USBDiscMonitor.DriveAvailable:
            temp = USBDiscMonitor.DfPath
            self.image_root = temp
            MainLog.Log(
                "folderhandler.__init__(): UsbFolder is specified for image storage. Using ",
                temp,
                terminal=False,
            )
        else:
            temp = self.project_root  # Default to the system SD card for storage.
            self.image_root = self.join_path(temp, "data")
            MainLog.Log(
                "folderhandler.__init__(): No UsbFolder is secified for image storage. Using ",
                temp,
                terminal=False,
            )
        self.data_root = self.join_path(
            projectroot, "data"
        )  # This structure should be setup and configured BEFORE running this program. For safety we don't mess with this here.
        # Create some default folders to get things running until the full structure is defined.
        self.new_session(
            campaign="campaign", session="session"
        )  # Create default folder entries. Will be updated when target chosen.

    def list_campaign_folders(self):
        """Return a list of campaign folders currently on disc."""
        rootpath = (
            self.get_path("imageroot") + "/campaign_*"
        )  # Where are the campaign folders held?
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def list_session_folders(self):
        """Return a list of session folders currently on disc."""
        rootpath = (
            self.get_path("imageroot") + "/campaign_*/session_*"
        )  # Where are the session folders held?
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def list_image_folders(self, imagetype="light"):
        """Return a list of image folders currently on disc.
        imagetype says which type of image folders to return."""
        rootpath = (
            self.get_path("imageroot") + "/campaign_*/session_*/" + imagetype
        )  # Where are the image folders held?
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def join_path(self, patha, pathb):
        """Perform JoinPath on both 'Path' and 'str' names.
        Return as str.

        Usage:
        fullpath = FolderList.JoinPath('/home/pi/pilomar','test.txt')
        sets fullpath to '/homepi/pilomar/test.txt'"""
        patha = self.to_path_type(patha)
        pathb = self.to_path_type(pathb)
        return str(Path.joinpath(patha, pathb))

    def valid_key(self, key):
        """Return TRUE if the key is recognised."""
        if key in self.folder_list:
            result = True
        else:
            result = False
        return result

    def prep_file(self, key, filename):
        """Given a folder KEY and a FILENAME construct the full path to the file
        and ensure that the destination folder exists.
        returns the fully qualified file path."""
        fullpath = self.join_path(
            self.get_path(key), filename
        )  # Construct full qualified path for the file.
        self.create_folder_from_list_entry(
            key
        )  # Make sure that the destination folder exists.
        return fullpath

    def new_session(self, campaign, session):
        """Given new campaign and session info, create the directory structure in the dictionary.
        Actual folders are not created yet. They are made on-demand.
        This creates the standard list of folders based upon the current campaign and session.
        To create a folder you must call

          folderhandler.PrepFile(key,filename)
              This creates the folder if required and returns the fully qualified path to the filename.
          or
          folderhandler.CreateFolderFromListEntry(key)
              This creates the folder if required."""
        self.folder_list = {}  # Initial empty list of folders and attributes.
        campaign = self.clean_filename(
            campaign
        ).lower()  # Standardise on lower case for campaign.
        session = self.clean_filename(
            session
        ).lower()  # Standardise on lower case for session.
        self.add_project_folder(
            key="imageroot", foldername=self.image_root
        )  # Root of folders for campaign (image) data.
        self.add_project_folder(
            key="dataroot", foldername=self.data_root
        )  # # Root of folders for other data (target lists, parameters etc).
        self.add_project_folder(
            key="log", foldername=self.join_path(self.project_root, "log")
        )  # Create folder relative to the Project root.
        self.add_project_folder(
            key="campaign", foldername=self.join_path(self.image_root, campaign)
        )  # The parent folder for the campaign. Which could store work over several nights.
        self.add_project_folder(
            key="temp", foldername=self.join_path(self.project_root, "temp")
        )  # Temporary folder for experiments.
        self.add_project_folder(
            key="session", foldername=self.join_path(self.get_path("campaign"), session)
        )  # The folder for an individual session.
        self.add_project_folder(
            key="tracking",
            foldername=self.join_path(self.get_path("session"), "tracking"),
        )  # This is the folder where tracking images are stored.
        self.add_project_folder(
            key="auto", foldername=self.join_path(self.get_path("session"), "auto")
        )  # This is the folder where automatic images are stored.
        self.add_project_folder(
            key="dark", foldername=self.join_path(self.get_path("session"), "dark")
        )  # The Pi-lomar folder for the DARK images.
        self.add_project_folder(
            key="darkflat",
            foldername=self.join_path(self.get_path("session"), "darkflat"),
        )  # The folder for the DARK FLAT images.
        self.add_project_folder(
            key="light", foldername=self.join_path(self.get_path("session"), "light")
        )  # The Pi-lomar folder for the LIGHT images. (The actual observations)
        self.add_project_folder(
            key="flat", foldername=self.join_path(self.get_path("session"), "flat")
        )  # The Pi-lomar folder for the FLAT images.
        self.add_project_folder(
            key="bias", foldername=self.join_path(self.get_path("session"), "bias")
        )  # The Pi-Lomar folder for the BIAS/OFFSET images.
        self.add_project_folder(
            key="preview",
            foldername=self.join_path(self.get_path("session"), "preview"),
        )  # The folder for the PREVIEW images.

    def print_folder_list(self):
        """Simple print of the current folder list."""
        print(TextColor.yellow("Current folder structure"))
        for key, value in self.folder_list.items():
            line = "- "
            line += key.ljust(10)[:10] + " "  # Column for key.
            if value["exists"]:  # Directory already exists.
                line += TextColor.green("exists ")
            else:
                line += TextColor.yellow("       ")
            line += TextColor.white(value["path"])
            print(line)

    def to_path_type(self, filepath):
        """Make sure filepath is a Path type.
        When referring to file and folder names in the code it is easy to confuse string and Path objects.
        This makes sure that you are always using a Path object by converting string values to Path objects.
        """
        if not isinstance(filepath, FolderHandler):
            filepath = FolderHandler(filepath)
        return filepath

    def get_path(self, key):
        """Given a folder key, return the folder name.

        The path for various folders changes with each observation session.
        This allows you to refer to a folder by it's purpose, and retrieve the current dynamic value.

        Usage:
          current_light_image_folder = folderhandler.GetPath('light')
          Returns something like '/home/pi/pilomar/data/campaign_saturn/session_20220514201436/light'
        """
        result = None
        if key in self.folder_list:
            result = self.folder_list[key].get("path", None)
        return result

    def add_project_folder(self, key, foldername):
        """Create a folder entry in FolderList.
        Does not immediately create the Folder."""
        foldername = self.clean_filename(foldername)  # Remove dangerous characters.
        foldername = self.to_path_type(foldername)  # Convert to Path object.
        folderpath = self.join_path(self.project_root, foldername)
        entry = {"path": str(folderpath), "exists": self.path_exists(folderpath)}
        self.folder_list[key] = entry

    def clean_filename(self, filename):
        """Remove dangerous characters from a filename or path."""
        filename = filename.replace(" ", "").replace("-", "").replace(":", "")
        filename = filename.replace("(", "").replace(")", "")
        return filename

    def path_exists(self, folderpath):
        """Return TRUE if a path exists. Else False."""
        folderpath = self.to_path_type(folderpath)  # Convert to Path object.
        return folderpath.exists()

    def is_file(self, folderpath):
        """Return TRUE if a path points to a file. Else False."""
        folderpath = self.to_path_type(folderpath)  # Convert to Path object.
        return folderpath.is_file()

    def is_dir(self, folderpath):
        """Return TRUE if a path points to a file. Else False."""
        folderpath = self.to_path_type(folderpath)  # Convert to Path object.
        return folderpath.is_dir()

    def create_folder_from_list_entry(self, key):
        """Given a folder key, make sure it exists and mark the entry accordingly."""
        if key in self.folder_list:  # Recognised entry in FolderList.
            if not self.folder_list[key]["exists"]:  # The folder does not exist yet.
                folderpath = self.get_path(key)  # Get the full path.
                self.create_folder_by_path(folderpath)  # Create the actual folder.
                self.folder_list[key][
                    "exists"
                ] = True  # Mark that the folder now exists.
                self.log(
                    "folderhandler.CreateFolderFromListEntry(",
                    key,
                    ") created folder:",
                    folderpath,
                    terminal=False,
                )
        else:
            self.log(
                "folderhandler.CreateFolderFromListEntry(",
                key,
                ") key does not exist.",
                terminal=False,
            )

    def create_folder_by_path(self, folderpath):
        """Make sure a directory exists.
        folderpath can include a destination filename, but it's ignored."""
        try:
            self.log(
                "folderhandler.CreateFolderByPath(", folderpath, ")", terminal=False
            )
            folderpath = self.to_path_type(folderpath)  # Convert to Path object.
            if folderpath.is_file():
                folderpath = (
                    folderpath.parent
                )  # Strip off any file name. Just want the folder structure.
            folderpath.mkdir(
                mode=0o777, parents=True, exist_ok=True
            )  # Create folder and all parent folders if missing.
        except Exception as e:
            MainLog.ReportException(
                e, command="folderhandler.CreateFolderByPath"
            )  # Trap all the exception information in the main log file.
