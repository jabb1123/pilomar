#!/usr/bin/python

# image class for use in Pilomar project.
# Builds upon opencv features to provide pilomar specific routines.
# Some methods are just simplifications of existing opencv routines, such as line drawing, circles, etc.
# Some methods are enhancements adding some more features to existing opencv functions.
# There are also some methods which are very specific to the pilomar miniature observatory project.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import cv2  # OpenCV.
import numpy as np  # Numpy array handling.
from datetime import datetime, timezone, timedelta
import math
import random  # random number generator.
import os
from PIL import Image as PIL_Image
from PIL import ExifTags as PIL_ExifTags


class DataSet:
    """Data set list of data points."""

    def __init__(self, name, color=None, style=["line"]):
        self.name = name
        self.data_points = []
        self.color = color
        self.style = style

    def add(self, point):
        self.data_points.append(point)

    def clear(self):
        self.data_points = []


class data_point:
    """Datapoint."""

    def __init__(
        self, x, y, color=None, label=None, style=["dot"], xname=None, yname=None
    ):
        self.x = x
        self.y = y
        self.color = color
        self.label = label
        self.style = style
        self.x_name = xname
        self.y_name = yname


class fd_object:
    """Object to be placed in an image (for force directed graphs)."""

    def __init__(self):
        self.name = None
        self.type = None
        self.width = None  # Dimensions of object.
        self.height = None
        self.initial_x = None  # Centre of object.
        self.initial_y = None
        self.fixed = False
        self.current_x = self.initial_x  # Centre of object.
        self.current_y = self.initial_y
        self.target_x = self.initial_x  # Centre of object.
        self.target_y = self.initial_y


class fd_edge:
    """Link between to objects (for force directed graphs)."""

    def __init__(self):
        self.name = None
        self.object_a = None  # Handle to object at one end of the edge.
        self.object_b = None  # Handle to object at the other end of the edge.


class PilomarImage:

    # Constants.
    __version__ = "0.1.0"
    IMAGETYPES = ["bgr", "bgra", "grayscale"]
    # COLORPOINTS is used to estimate a RGB color from a Hipparcos star catalog star B-V value.
    COLORPOINTS = [
        (-0.33, [0x70, 0x6F, 0xFE]),
        (-0.3, [0x51, 0x9F, 0xFE]),
        (-0.02, [0xBF, 0xD0, 0xFF]),
        (0.3, [0xCD, 0xFD, 0xFF]),
        (0.58, [0xEE, 0xFF, 0xDF]),
        (0.81, [0xFF, 0xFF, 0x7F]),
        (1.4, [0xFE, 0x7F, 0x7D]),
    ]
    # Color names for OpenCV drawing. (Beware colors are BGR not RGB!)
    # Official HTML colors 3 Channel BGR colors only.
    # Make all BGR colors available as a dictionary. Easier to search and manipulate.
    BGRColor = {
        "Black": (0, 0, 0),
        "Night": (10, 9, 12),
        "Charcoal": (44, 40, 52),
        "Oil": (49, 49, 59),
        "DarkGray": (60, 59, 58),
        "LightBlack": (69, 69, 69),
        "BlackCat": (57, 56, 65),
        "Iridium": (58, 60, 61),
        "BlackEel": (63, 62, 70),
        "BlackCow": (70, 70, 76),
        "GrayWolf": (75, 74, 80),
        "VampireGray": (81, 80, 86),
        "IronGray": (93, 89, 82),
        "GrayDolphin": (88, 88, 92),
        "CarbonGray": (93, 93, 98),
        "AshGray": (98, 99, 102),
        "DimGray": (105, 105, 105),
        "NardoGray": (108, 106, 104),
        "CloudyGray": (104, 105, 109),
        "SmokeyGray": (109, 110, 114),
        "AlienGray": (110, 111, 115),
        "SonicSilver": (117, 117, 117),
        "PlatinumGray": (121, 121, 121),
        "Granite": (124, 126, 131),
        "Gray": (128, 128, 128),
        "BattleshipGray": (130, 132, 132),
        "GunmetalGray": (141, 145, 141),
        "DarkGray": (169, 169, 169),
        "GrayCloud": (180, 182, 182),
        "Silver": (192, 192, 192),
        "PaleSilver": (187, 192, 201),
        "GrayGoose": (206, 208, 209),
        "PlatinumSilver": (206, 206, 206),
        "LightGray": (211, 211, 211),
        "SilverWhite": (221, 219, 218),
        "Gainsboro": (220, 220, 220),
        "Platinum": (226, 228, 229),
        "MetallicSilver": (204, 198, 188),
        "BlueGray": (199, 175, 152),
        "RomanSilver": (150, 137, 131),
        "LightSlateGray": (153, 136, 119),
        "SlateGray": (144, 128, 112),
        "RatGray": (141, 123, 109),
        "SlateGraniteGray": (131, 115, 101),
        "JetGray": (126, 109, 97),
        "MistBlue": (126, 109, 100),
        "MarbleBlue": (126, 109, 86),
        "SlateBlueGrey": (161, 124, 115),
        "LightPurpleBlue": (206, 143, 114),
        "AzureBlue": (160, 99, 72),
        "BlueJay": (126, 84, 43),
        "CharcoalBlue": (79, 69, 54),
        "DarkBlueGrey": (91, 70, 41),
        "DarkSlate": (86, 56, 43),
        "DeepSeaBlue": (86, 52, 18),
        "NightBlue": (84, 27, 21),
        "MidnightBlue": (112, 25, 25),
        "Navy": (128, 0, 0),
        "DenimDarkBlue": (141, 27, 21),
        "DarkBlue": (139, 0, 0),
        "LapisBlue": (126, 49, 21),
        "NewMidnightBlue": (160, 0, 0),
        "EarthBlue": (165, 0, 0),
        "CobaltBlue": (194, 32, 0),
        "MediumBlue": (205, 0, 0),
        "BlueberryBlue": (194, 65, 0),
        "CanaryBlue": (245, 22, 41),
        "Blue": (255, 0, 0),
        "SamcoBlue": (255, 2, 0),
        "BrightBlue": (255, 9, 9),
        "BlueOrchid": (252, 69, 31),
        "SapphireBlue": (199, 84, 37),
        "BlueEyes": (199, 105, 21),
        "BrightNavyBlue": (210, 116, 25),
        "BalloonBlue": (222, 96, 43),
        "RoyalBlue": (225, 105, 65),
        "OceanBlue": (236, 101, 43),
        "BlueRibbon": (255, 110, 48),
        "BlueDress": (236, 125, 21),
        "NeonBlue": (255, 137, 21),
        "DodgerBlue": (255, 144, 30),
        "GlacialBlueIce": (193, 139, 54),
        "SteelBlue": (180, 130, 70),
        "SilkBlue": (199, 138, 72),
        "WindowsBlue": (199, 126, 53),
        "BlueIvy": (199, 144, 48),
        "BlueKoi": (199, 158, 101),
        "ColumbiaBlue": (199, 175, 135),
        "BabyBlue": (199, 185, 149),
        "CornflowerBlue": (237, 149, 100),
        "SkyBlueDress": (255, 152, 102),
        "Iceberg": (236, 165, 86),
        "ButterflyBlue": (236, 172, 56),
        "DeepSkyBlue": (255, 191, 0),
        "MiddayBlue": (255, 185, 59),
        "CrystalBlue": (255, 179, 92),
        "DenimBlue": (236, 186, 121),
        "DaySkyBlue": (255, 202, 130),
        "LightSkyBlue": (250, 206, 135),
        "SkyBlue": (235, 206, 135),
        "JeansBlue": (236, 207, 160),
        "BlueAngel": (236, 206, 183),
        "PastelBlue": (236, 207, 180),
        "LightDayBlue": (255, 223, 173),
        "SeaBlue": (255, 223, 194),
        "HeavenlyBlue": (255, 222, 198),
        "RobinEggBlue": (255, 237, 189),
        "PowderBlue": (230, 224, 176),
        "CoralBlue": (236, 220, 175),
        "LightBlue": (230, 216, 173),
        "LightSteelBlue": (222, 207, 176),
        "GulfBlue": (236, 223, 201),
        "PastelLightBlue": (234, 214, 213),
        "LavenderBlue": (250, 228, 227),
        "WhiteBlue": (250, 233, 219),
        "Lavender": (250, 230, 230),
        "Water": (250, 244, 235),
        "AliceBlue": (255, 248, 240),
        "GhostWhite": (255, 248, 248),
        "Azure": (255, 255, 240),
        "LightCyan": (255, 255, 224),
        "LightSlate": (255, 255, 204),
        "ElectricBlue": (255, 254, 154),
        "TronBlue": (254, 253, 125),
        "BlueZircon": (255, 254, 87),
        "Aqua": (255, 255, 0),
        "Cyan": (255, 255, 0),
        "BrightCyan": (255, 255, 10),
        "Celeste": (236, 235, 80),
        "BlueDiamond": (236, 226, 78),
        "BrightTurquoise": (245, 226, 22),
        "BlueLagoon": (236, 235, 142),
        "PaleTurquoise": (238, 238, 175),
        "PaleBlueLily": (236, 236, 207),
        "LightTeal": (217, 217, 179),
        "TiffanyBlue": (208, 216, 129),
        "BlueHosta": (199, 191, 119),
        "CyanOpaque": (199, 199, 146),
        "NorthernLightsBlue": (199, 199, 120),
        "BlueGreen": (181, 204, 123),
        "MediumAquaMarine": (170, 205, 102),
        "MagicMint": (209, 240, 170),
        "LightAquamarine": (232, 255, 147),
        "Aquamarine": (212, 255, 127),
        "BrightTeal": (198, 249, 1),
        "Turquoise": (208, 224, 64),
        "MediumTurquoise": (204, 209, 72),
        "DeepTurquoise": (205, 204, 72),
        "Jellyfish": (199, 199, 70),
        "BlueTurquoise": (219, 198, 67),
        "DarkTurquoise": (209, 206, 0),
        "MacawBlueGreen": (199, 191, 67),
        "LightSeaGreen": (170, 178, 32),
        "SeafoamGreen": (159, 169, 62),
        "CadetBlue": (160, 158, 95),
        "DeepSea": (156, 156, 59),
        "DarkCyan": (139, 139, 0),
        "TealGreen": (127, 130, 0),
        "Teal": (128, 128, 0),
        "TealBlue": (128, 124, 0),
        "MediumTeal": (95, 95, 4),
        "DarkTeal": (93, 93, 4),
        "DeepTeal": (62, 62, 3),
        "DarkSlateGray": (60, 56, 37),
        "Gunmetal": (57, 53, 44),
        "BlueMossGreen": (91, 86, 60),
        "BeetleGreen": (126, 120, 76),
        "GrayishTurquoise": (126, 125, 94),
        "GreenishBlue": (126, 125, 48),
        "AquamarineStone": (129, 135, 52),
        "SeaTurtleGreen": (128, 141, 67),
        "DullSeaGreen": (117, 137, 78),
        "DarkGreenBlue": (87, 99, 31),
        "DeepSeaGreen": (84, 103, 48),
        "BottleGreen": (78, 106, 0),
        "SeaGreen": (87, 139, 46),
        "ElfGreen": (107, 138, 27),
        "DarkMint": (110, 144, 49),
        "Jade": (108, 163, 0),
        "EarthGreen": (111, 165, 52),
        "ChromeGreen": (96, 162, 26),
        "Emerald": (120, 200, 80),
        "Mint": (137, 180, 62),
        "MediumSeaGreen": (113, 179, 60),
        "MetallicGreen": (142, 157, 124),
        "CamouflageGreen": (107, 134, 120),
        "SageGreen": (121, 139, 132),
        "HazelGreen": (88, 124, 97),
        "VenomGreen": (0, 140, 114),
        "OliveDrab": (35, 142, 107),
        "Olive": (0, 128, 128),
        "DarkOliveGreen": (47, 107, 85),
        "MilitaryGreen": (49, 91, 78),
        "GreenLeaves": (11, 95, 58),
        "ArmyGreen": (32, 83, 75),
        "FernGreen": (38, 124, 102),
        "FallForestGreen": (88, 146, 78),
        "IrishGreen": (75, 160, 8),
        "PineGreen": (68, 124, 56),
        "MediumForestGreen": (53, 114, 52),
        "JungleGreen": (44, 124, 52),
        "CactusGreen": (66, 116, 34),
        "ForestGreen": (34, 139, 34),
        "Green": (0, 128, 0),
        "DarkGreen": (0, 100, 0),
        "DeepGreen": (8, 102, 5),
        "DeepEmeraldGreen": (7, 99, 4),
        "HunterGreen": (59, 94, 53),
        "DarkForestGreen": (23, 65, 37),
        "LotusGreen": (37, 66, 0),
        "SeaweedGreen": (23, 124, 67),
        "ShamrockGreen": (23, 124, 52),
        "GreenOnion": (33, 161, 106),
        "MossGreen": (91, 154, 138),
        "GrassGreen": (11, 155, 63),
        "GreenPepper": (44, 160, 74),
        "DarkLimeGreen": (23, 163, 65),
        "ParrotGreen": (43, 173, 18),
        "CloverGreen": (85, 160, 62),
        "DinosaurGreen": (108, 161, 115),
        "GreenSnake": (60, 187, 108),
        "AlienGreen": (23, 196, 108),
        "GreenApple": (23, 196, 76),
        "LimeGreen": (50, 205, 50),
        "PeaGreen": (23, 208, 82),
        "KellyGreen": (82, 197, 76),
        "ZombieGreen": (113, 197, 84),
        "GreenPeas": (92, 195, 137),
        "DollarBillGreen": (101, 187, 133),
        "FrogGreen": (142, 198, 153),
        "TurquoiseGreen": (180, 214, 160),
        "DarkSeaGreen": (143, 188, 143),
        "BasilGreen": (130, 159, 130),
        "GrayGreen": (156, 173, 162),
        "IguanaGreen": (113, 176, 156),
        "CitronGreen": (29, 179, 143),
        "AcidGreen": (26, 191, 176),
        "AvocadoGreen": (72, 194, 178),
        "PistachioGreen": (9, 194, 157),
        "SaladGreen": (53, 201, 161),
        "YellowGreen": (50, 205, 154),
        "PastelGreen": (119, 221, 119),
        "HummingbirdGreen": (23, 232, 127),
        "NebulaGreen": (23, 232, 89),
        "StoplightGoGreen": (100, 233, 87),
        "NeonGreen": (41, 245, 22),
        "JadeGreen": (110, 251, 94),
        "LimeMintGreen": (127, 245, 54),
        "SpringGreen": (127, 255, 0),
        "MediumSpringGreen": (154, 250, 0),
        "EmeraldGreen": (23, 251, 95),
        "Lime": (0, 255, 0),
        "LawnGreen": (0, 252, 124),
        "BrightGreen": (0, 255, 102),
        "Chartreuse": (0, 255, 127),
        "YellowLawnGreen": (23, 247, 135),
        "AloeVeraGreen": (22, 245, 152),
        "DullGreenYellow": (23, 251, 177),
        "LemonGreen": (2, 248, 173),
        "GreenYellow": (47, 255, 173),
        "ChameleonGreen": (22, 245, 189),
        "NeonYellowGreen": (1, 238, 218),
        "YellowGreenGrosbeak": (22, 245, 226),
        "TeaGreen": (93, 251, 204),
        "SlimeGreen": (84, 233, 188),
        "AlgaeGreen": (134, 233, 100),
        "LightGreen": (144, 238, 144),
        "DragonGreen": (146, 251, 106),
        "PaleGreen": (152, 251, 152),
        "MintGreen": (152, 255, 152),
        "GreenThumb": (170, 234, 181),
        "OrganicBrown": (166, 249, 227),
        "LightJade": (184, 253, 195),
        "LightMintGreen": (211, 229, 194),
        "LightRoseGreen": (219, 249, 219),
        "ChromeWhite": (212, 241, 232),
        "HoneyDew": (240, 255, 240),
        "MintCream": (250, 255, 245),
        "LemonChiffon": (205, 250, 255),
        "Parchment": (194, 255, 255),
        "Cream": (204, 255, 255),
        "CreamWhite": (208, 253, 255),
        "LightGoldenRodYellow": (210, 250, 250),
        "LightYellow": (224, 255, 255),
        "Beige": (220, 245, 245),
        "Cornsilk": (220, 248, 255),
        "Blonde": (217, 246, 251),
        "Champagne": (206, 231, 247),
        "AntiqueWhite": (215, 235, 250),
        "PapayaWhip": (213, 239, 255),
        "BlanchedAlmond": (205, 235, 255),
        "Bisque": (196, 228, 255),
        "Wheat": (179, 222, 245),
        "Moccasin": (181, 228, 255),
        "Peach": (180, 229, 255),
        "LightOrange": (177, 216, 254),
        "PeachPuff": (185, 218, 255),
        "CoralPeach": (171, 213, 251),
        "NavajoWhite": (173, 222, 255),
        "GoldenBlonde": (161, 231, 251),
        "GoldenSilk": (195, 227, 243),
        "DarkBlonde": (182, 226, 240),
        "LightGold": (172, 229, 241),
        "Vanilla": (171, 229, 243),
        "TanBrown": (182, 229, 236),
        "DirtyWhite": (201, 228, 232),
        "PaleGoldenRod": (170, 232, 238),
        "Khaki": (140, 230, 240),
        "CardboardBrown": (116, 218, 237),
        "HarvestGold": (117, 226, 237),
        "SunYellow": (124, 232, 255),
        "CornYellow": (128, 243, 255),
        "PastelYellow": (132, 248, 250),
        "NeonYellow": (51, 255, 255),
        "Yellow": (0, 255, 255),
        "CanaryYellow": (0, 239, 255),
        "BananaYellow": (22, 226, 245),
        "MustardYellow": (88, 219, 255),
        "GoldenYellow": (0, 223, 255),
        "BoldYellow": (36, 219, 249),
        "RubberDuckyYellow": (1, 216, 255),
        "Gold": (0, 215, 255),
        "BrightGold": (23, 208, 253),
        "ChromeGold": (68, 206, 255),
        "GoldenBrown": (23, 193, 234),
        "DeepYellow": (0, 190, 246),
        "MacaroniandCheese": (102, 187, 242),
        "Saffron": (23, 185, 251),
        "NeonGold": (1, 189, 253),
        "Beer": (23, 177, 251),
        "OrangeYellow": (66, 174, 255),
        "YellowOrange": (66, 174, 255),
        "Cantaloupe": (47, 166, 255),
        "CheeseOrange": (0, 166, 255),
        "Orange": (0, 165, 255),
        "BrownSand": (77, 154, 238),
        "SandyBrown": (96, 164, 244),
        "BrownSugar": (111, 167, 226),
        "CamelBrown": (107, 154, 193),
        "DeerBrown": (131, 191, 230),
        "BurlyWood": (135, 184, 222),
        "Tan": (140, 180, 210),
        "LightFrenchBeige": (127, 173, 200),
        "Sand": (128, 178, 194),
        "Sage": (138, 184, 188),
        "FallLeafBrown": (96, 181, 200),
        "GingerBrown": (98, 190, 201),
        "BronzeGold": (93, 174, 201),
        "DarkKhaki": (107, 183, 189),
        "OliveGreen": (108, 184, 186),
        "Brass": (66, 166, 181),
        "CookieBrown": (23, 163, 199),
        "MetallicGold": (55, 175, 212),
        "BeeYellow": (23, 171, 233),
        "SchoolBusYellow": (23, 163, 232),
        "GoldenRod": (32, 165, 218),
        "OrangeGold": (23, 160, 212),
        "Caramel": (23, 142, 198),
        "DarkGoldenRod": (11, 134, 184),
        "Cinnamon": (23, 137, 197),
        "Peru": (63, 133, 205),
        "Bronze": (50, 127, 205),
        "TigerOrange": (65, 129, 200),
        "Copper": (51, 115, 184),
        "DarkGold": (57, 108, 170),
        "MetallicBronze": (66, 113, 169),
        "DarkAlmond": (78, 120, 171),
        "Wood": (51, 111, 150),
        "OakBrown": (23, 101, 128),
        "AntiqueBronze": (30, 93, 102),
        "Hazel": (24, 118, 142),
        "DarkYellow": (0, 128, 139),
        "DarkMoccasin": (57, 120, 130),
        "KhakiGreen": (93, 134, 138),
        "MillenniumJade": (124, 145, 147),
        "DarkBeige": (118, 140, 159),
        "BulletShell": (96, 155, 175),
        "ArmyBrown": (96, 123, 130),
        "Sandstone": (95, 109, 120),
        "Taupe": (50, 60, 72),
        "Mocha": (38, 61, 73),
        "MilkChocolate": (28, 59, 81),
        "GrayBrown": (53, 54, 61),
        "DarkCoffee": (47, 47, 59),
        "OldBurgundy": (46, 48, 67),
        "WesternCharcoal": (63, 65, 73),
        "BakersBrown": (23, 51, 92),
        "DarkBrown": (33, 67, 101),
        "SepiaBrown": (20, 66, 112),
        "DarkBronze": (0, 74, 128),
        "Coffee": (55, 78, 111),
        "BrownBear": (59, 92, 131),
        "RedDirt": (23, 82, 127),
        "Sepia": (44, 70, 127),
        "Sienna": (45, 82, 160),
        "SaddleBrown": (19, 69, 139),
        "DarkSienna": (23, 65, 138),
        "Sangria": (23, 56, 126),
        "BloodRed": (23, 53, 126),
        "Chestnut": (53, 69, 149),
        "CoralBrown": (56, 70, 158),
        "ChestnutRed": (44, 74, 195),
        "Mahogany": (0, 64, 192),
        "RedGold": (6, 84, 235),
        "RedFox": (23, 88, 195),
        "DarkBisque": (0, 101, 184),
        "LightBrown": (29, 101, 181),
        "PetraGold": (52, 103, 183),
        "Rust": (65, 98, 195),
        "CopperRed": (81, 109, 203),
        "OrangeSalmon": (81, 116, 196),
        "Chocolate": (30, 105, 210),
        "Sedona": (0, 102, 204),
        "PapayaOrange": (23, 103, 229),
        "HalloweenOrange": (44, 108, 230),
        "NeonOrange": (0, 103, 255),
        "BrightOrange": (31, 95, 255),
        "PumpkinOrange": (23, 114, 248),
        "CarrotOrange": (23, 128, 248),
        "DarkOrange": (0, 140, 255),
        "ConstructionConeOrange": (49, 116, 248),
        "IndianSaffron": (34, 119, 255),
        "SunriseOrange": (81, 116, 230),
        "MangoOrange": (64, 128, 255),
        "Coral": (80, 127, 255),
        "BasketBallOrange": (88, 129, 248),
        "LightSalmonRose": (107, 150, 249),
        "LightSalmon": (122, 160, 255),
        "DarkSalmon": (122, 150, 233),
        "Tangerine": (97, 138, 231),
        "LightCopper": (103, 138, 218),
        "SalmonPink": (116, 134, 255),
        "Salmon": (114, 128, 250),
        "PeachPink": (136, 139, 249),
        "LightCoral": (128, 128, 240),
        "PastelRed": (128, 114, 246),
        "PinkCoral": (113, 116, 231),
        "BeanRed": (89, 93, 247),
        "ValentineRed": (81, 84, 229),
        "IndianRed": (92, 92, 205),
        "Tomato": (71, 99, 255),
        "ShockingOrange": (60, 91, 229),
        "OrangeRed": (0, 69, 255),
        "Red": (0, 0, 255),
        "NeonRed": (3, 28, 253),
        "ScarletRed": (0, 36, 255),
        "RubyRed": (23, 34, 246),
        "FerrariRed": (26, 13, 247),
        "FireEngineRed": (23, 40, 246),
        "LavaRed": (23, 34, 228),
        "LoveRed": (23, 27, 228),
        "Grapefruit": (31, 56, 220),
        "CherryRed": (65, 70, 194),
        "ChilliPepper": (23, 27, 193),
        "FireBrick": (34, 34, 178),
        "TomatoSauceRed": (7, 24, 178),
        "Brown": (42, 42, 165),
        "CarbonRed": (42, 13, 167),
        "Cranberry": (15, 0, 159),
        "SaffronRed": (20, 19, 147),
        "CrimsonRed": (0, 0, 153),
        "RedWine": (18, 0, 153),
        "WineRed": (18, 0, 153),
        "DarkRed": (0, 0, 139),
        "VeryDarkRed": (0, 0, 10),
        "Maroon": (0, 0, 128),
        "Burgundy": (26, 0, 140),
        "Vermilion": (27, 25, 126),
        "DeepRed": (23, 5, 128),
        "RedBlood": (0, 0, 102),
        "BloodNight": (6, 22, 85),
        "DarkScarlet": (25, 3, 86),
        "BlackBean": (2, 12, 61),
        "ChocolateBrown": (15, 0, 63),
        "Midnight": (23, 27, 43),
        "PurpleLily": (53, 10, 85),
        "PurpleMaroon": (65, 5, 129),
        "PlumPie": (65, 5, 125),
        "PlumVelvet": (82, 5, 125),
        "DarkRaspberry": (87, 38, 135),
        "VelvetMaroon": (77, 53, 126),
        "RosyFinch": (82, 78, 127),
        "DullPurple": (93, 82, 127),
        "Puce": (88, 90, 127),
        "RoseDust": (112, 112, 153),
        "PastelBrown": (127, 144, 177),
        "RosyPink": (129, 132, 179),
        "RosyBrown": (143, 143, 188),
        "KhakiRose": (142, 144, 197),
        "LipstickPink": (147, 135, 196),
        "PinkBrown": (137, 129, 196),
        "OldRose": (129, 128, 192),
        "DustyPink": (148, 138, 213),
        "PinkDaisy": (163, 153, 231),
        "Rose": (170, 173, 232),
        "DustyRose": (166, 169, 201),
        "SilverPink": (173, 174, 196),
        "GoldPink": (194, 199, 230),
        "RoseGold": (192, 197, 236),
        "DeepPeach": (164, 203, 255),
        "PastelOrange": (139, 184, 248),
        "DesertSand": (175, 201, 237),
        "UnbleachedSilk": (202, 221, 255),
        "PigPink": (228, 215, 253),
        "PalePink": (215, 212, 242),
        "Blush": (232, 230, 255),
        "MistyRose": (225, 228, 255),
        "PinkBubbleGum": (221, 223, 255),
        "LightRose": (205, 207, 251),
        "LightRed": (203, 204, 255),
        "WarmPink": (189, 198, 246),
        "DeepRose": (185, 187, 251),
        "Pink": (203, 192, 255),
        "LightPink": (193, 182, 255),
        "SoftPink": (191, 184, 255),
        "DonutPink": (190, 175, 250),
        "BabyPink": (186, 175, 250),
        "FlamingoPink": (176, 167, 249),
        "PastelPink": (170, 163, 254),
        "RosePink": (176, 161, 231),
        "PinkRose": (176, 161, 231),
        "CadillacPink": (174, 138, 227),
        "CarnationPink": (161, 120, 247),
        "PastelRose": (143, 120, 229),
        "BlushRed": (148, 110, 229),
        "PaleVioletRed": (147, 112, 219),
        "PurplePink": (135, 101, 209),
        "TulipPink": (124, 90, 194),
        "BashfulPink": (131, 82, 194),
        "DarkPink": (128, 84, 231),
        "DarkHotPink": (171, 96, 246),
        "HotPink": (180, 105, 255),
        "WatermelonPink": (133, 108, 252),
        "VioletRed": (138, 53, 246),
        "HotDeepPink": (135, 40, 245),
        "BrightPink": (127, 0, 255),
        "DeepPink": (147, 20, 255),
        "NeonPink": (170, 53, 245),
        "ChromePink": (170, 51, 255),
        "NeonHotPink": (156, 52, 253),
        "PinkCupcake": (157, 94, 228),
        "RoyalPink": (172, 89, 231),
        "DimorphothecaMagenta": (157, 49, 227),
        "PinkLemonade": (124, 40, 228),
        "RedPink": (85, 42, 250),
        "Raspberry": (93, 11, 227),
        "Crimson": (60, 20, 220),
        "BrightMaroon": (72, 33, 195),
        "RoseRed": (86, 30, 194),
        "RoguePink": (105, 40, 193),
        "BurntPink": (103, 34, 193),
        "PinkViolet": (107, 34, 202),
        "MagentaPink": (139, 51, 204),
        "MediumVioletRed": (133, 21, 199),
        "DarkCarnationPink": (131, 34, 193),
        "RaspberryPurple": (108, 68, 179),
        "PinkPlum": (143, 59, 185),
        "Orchid": (214, 112, 218),
        "DeepMauve": (212, 115, 223),
        "Violet": (238, 130, 238),
        "FuchsiaPink": (255, 119, 255),
        "BrightNeonPink": (255, 51, 244),
        "Fuchsia": (255, 0, 255),
        "Magenta": (255, 0, 255),
        "CrimsonPurple": (236, 56, 226),
        "HeliotropePurple": (255, 98, 212),
        "TyrianPurple": (236, 90, 196),
        "MediumOrchid": (211, 85, 186),
        "PurpleFlower": (199, 74, 167),
        "OrchidPurple": (181, 72, 176),
        "RichLilac": (210, 102, 182),
        "PastelViolet": (188, 145, 210),
        "MauveTaupe": (109, 95, 145),
        "ViolaPurple": (126, 88, 126),
        "Eggplant": (81, 64, 97),
        "PlumPurple": (89, 55, 88),
        "Grape": (128, 90, 94),
        "PurpleNavy": (128, 81, 78),
        "SlateBlue": (205, 90, 106),
        "BlueLotus": (236, 96, 105),
        "Blurple": (242, 101, 88),
        "LightSlateBlue": (255, 106, 115),
        "MediumSlateBlue": (238, 104, 123),
        "PeriwinklePurple": (207, 117, 117),
        "VeryPeri": (171, 103, 102),
        "BrightGrape": (168, 45, 111),
        "PurpleAmethyst": (199, 45, 108),
        "BrightPurple": (173, 13, 106),
        "DeepPeriwinkle": (166, 83, 84),
        "DarkSlateBlue": (139, 61, 72),
        "PurpleHaze": (126, 56, 78),
        "PurpleIris": (126, 27, 87),
        "DarkPurple": (80, 1, 75),
        "DeepPurple": (63, 1, 54),
        "MidnightPurple": (71, 26, 46),
        "PurpleMonster": (126, 27, 70),
        "Indigo": (130, 0, 75),
        "BlueWhale": (126, 45, 52),
        "RebeccaPurple": (153, 51, 102),
        "PurpleJam": (126, 40, 106),
        "DarkMagenta": (139, 0, 139),
        "Purple": (128, 0, 128),
        "FrenchLilac": (142, 96, 134),
        "DarkOrchid": (204, 50, 153),
        "DarkViolet": (211, 0, 148),
        "PurpleViolet": (201, 56, 141),
        "JasminePurple": (236, 59, 162),
        "PurpleDaffodil": (255, 65, 176),
        "ClematisViolet": (206, 45, 132),
        "BlueViolet": (226, 43, 138),
        "PurpleSageBush": (199, 93, 122),
        "LovelyPurple": (236, 56, 127),
        "NeonPurple": (255, 0, 157),
        "PurplePlum": (239, 53, 142),
        "AztechPurple": (255, 59, 137),
        "MediumPurple": (219, 112, 147),
        "LightPurple": (215, 103, 132),
        "CrocusPurple": (236, 114, 145),
        "PurpleMimosa": (255, 123, 158),
        "Periwinkle": (255, 204, 204),
        "PaleLilac": (255, 208, 220),
        "LavenderPurple": (182, 123, 150),
        "RosePurple": (202, 159, 176),
        "Lilac": (200, 162, 200),
        "Mauve": (255, 176, 224),
        "BrightLilac": (239, 145, 216),
        "PurpleDragon": (199, 142, 195),
        "Plum": (221, 160, 221),
        "BlushPink": (236, 169, 230),
        "PastelPurple": (232, 162, 242),
        "BlossomPink": (255, 183, 249),
        "WisteriaPurple": (199, 174, 198),
        "PurpleThistle": (211, 185, 210),
        "Thistle": (216, 191, 216),
        "PurpleWhite": (227, 211, 223),
        "PeriwinklePink": (236, 207, 233),
        "CottonCandy": (255, 223, 252),
        "LavenderPinocchio": (226, 221, 235),
        "DarkWhite": (209, 217, 225),
        "AshWhite": (212, 228, 233),
        "WhiteChocolate": (214, 230, 237),
        "SoftIvory": (221, 240, 250),
        "OffWhite": (227, 240, 248),
        "PearlWhite": (240, 246, 248),
        "RedWhite": (234, 232, 243),
        "LavenderBlush": (245, 240, 255),
        "Pearl": (244, 238, 253),
        "EggShell": (227, 249, 255),
        "OldLace": (227, 240, 254),
        "Linen": (230, 240, 250),
        "SeaShell": (238, 245, 255),
        "BoneWhite": (238, 246, 249),
        "Rice": (239, 245, 250),
        "FloralWhite": (240, 250, 255),
        "Ivory": (240, 255, 255),
        "WhiteGold": (244, 255, 255),
        "LightWhite": (247, 255, 255),
        "WhiteSmoke": (245, 245, 245),
        "Cotton": (249, 251, 251),
        "Snow": (250, 250, 255),
        "MilkWhite": (255, 252, 254),
        "HalfWhite": (250, 254, 255),
        "White": (255, 255, 255),
    }

    @staticmethod
    def bgr(colorname):
        """Return color tuple for any given name."""
        return PilomarImage.BGRColor.get(colorname, (0, 0, 0))

    BGRAColor = {
        "Black": (0, 0, 0, 255),
        "Blue": (255, 0, 0, 255),
        "Cyan": (255, 255, 0, 255),
        "DimGray": (105, 105, 105, 255),
        "Gold": (0, 215, 255, 255),
        "Green": (0, 255, 0, 255),
        "HotPink": (180, 105, 255, 255),
        "LimeGreen": (50, 205, 50, 255),
        "Orange": (0, 165, 255, 255),
        "PaleGreen": (152, 251, 152, 255),
        "Red": (0, 0, 255, 255),
        "Transparent": (0, 0, 0, 0),
        "White": (255, 255, 255, 255),
        "Yellow": (0, 255, 255, 255),
    }

    @staticmethod
    def bgra(colorname):
        """Return color tuple for any given name."""
        return PilomarImage.BGRAColor.get(colorname, (0, 0, 0, 255))

    GRAYSCALEColor = {"White": 255, "50": 127, "Black": 0}

    @staticmethod
    def grayscale(colorname):
        """Return grayscale tuple for any given name."""
        return PilomarImage.GRAYSCALEColor.get(colorname, 0)

    # Define default filter scripts.
    # - You can overwrite this with your own set of scripts by assigning pilomarimage.FILTERSCRIPTS = {.....}
    # - This default script includes some example scripts to test, and also some specific scripts designed to achieve specific image enhancements.
    # - To run a script against the current image buffer call self.run_filter_script( filtername )
    # -  eg self.run_filter_script('ExampleThreshold') to run the ExampleThreshold script.
    # The scripts consist of a series of opencv actions that you can run against the current image buffer.
    # A script contains at least 1 action. Actions are executed their sequence in the script. The result is always stored in the current image buffer.
    # Where an action supports parameters those can be defined inside each step in this script.
    # If parameters are not given, defaults will be used.
    FILTERSCRIPTS = {
        "ExampleThreshold": {  # Example script to perform thresholding on an image. Call this with self.run_filter_script('ExampleThreshold')
            "ThresholdStep": {
                "method": "threshold",
                "threshold": 100,
                "maxval": 255,
                "type": cv2.THRESH_BINARY,
                "comment": "Use simple binary threshold to detect any pixels > 100 and consider them to be stars.",
            }  # /ThresholdStep
        },  # /ExampleThreshold
        "ExampleDehaze": {  # Example script to remove haze from the background of an image. Call this with self.run_filter_script('ExampleDehaze')
            "DeHaze": {
                "method": "dehaze",
                "samples": 1,
                "strength": 100,
                "comment": "Remove urban haze from the image background.",
            }  # /ExampleDehaze
        },
        "ExampleBlur": {  # Example script to perform gaussian blurring on the image. Call this with self.run_filter_script('ExampleBlur')
            "BlurStep": {
                "method": "gaussianblur",
                "radius": 100,
                "comment": "Apply Gaussian blur to widen remaining items",
            }  # /BlurStep
        },  # /ExampleBlur
        "ExampleGrayscale": {  # Example script to convert an image to grayscale. Call this with self.run_filter_script('ExampleGrayscale')
            "GrayStep": {
                "method": "grayscale",
                "comment": "Reduce an image to grayscale.",
            }  # /GrayStep
        },  # /ExampleGrayscale
        "EnhanceClouds": {  # Enhance clouds in the image.  Call this with self.run_filter_script('EnhanceClouds')
            "CloudThreshold": {
                "method": "threshold",
                "threshold": 100,
                "maxval": 255,
                "type": cv2.THRESH_BINARY,
                "comment": "Use simple binary threshold to detect any pixels > 100 and consider them to be potential clouds.",
            }  # /CloudThreshold
        },  # /CloudDetection
        "EnhanceStars": {  # Enhance stars in the image.  Call this with self.run_filter_script('EnhanceStars')
            "ToGrayscale": {  # Convert to grayscale image.
                "method": "grayscale",
            },  # /ToGrayscale
            "EliminateClouds": {  # Set low threshold to remove clouds and low level light.
                "method": "threshold",
                "threshold": 100,
                "maxval": 255,
                "type": cv2.THRESH_BINARY,
                "comment": "Apply low threshold to remove dim objects such as clouds.",
            },  # /EliminateClouds
            "BlurStars": {  # Use blur to enlarge remaining stars.
                "method": "gaussianblur",
                "radius": 13,
                "comment": "Apply Gaussian blur to widen remaining items",
            },  # /BlurStars
            "BoostStars": {  # Enhance remaining stars.
                "method": "threshold",
                "threshold": 16,
                "maxval": 255,
                "type": cv2.THRESH_BINARY + cv2.THRESH_OTSU,
                "comment": "Apply adaptive threshold to boost remaining stars.",
            },  # /BoostStars
        },  # /EnhanceStars
        "UrbanFilter": {  # UrbanFilter script. Reduce haze and enhance stars. Call this with self.run_filter_script('UrbanFilter')
            "ToGrayscale": {  # Convert to grayscale image.
                "method": "grayscale",
            },  # /ToGrayscale
            "DeHaze": {  # Reduce haze across the image.
                "method": "dehaze",
                "samples": 1,  # Just a single sample value is generated from the entire width of the line.
                "strength": 100,
                "comment": "Remove urban haze from the image background.",
            },  # /DeHaze
            "BlurStars": {  # Use blur to enlarge remaining stars.
                "method": "gaussianblur",
                "radius": 2,
                "comment": "Apply Gaussian blur to widen remaining items",
            },  # /BlurStars
            "BoostStars": {  # Enhance remaining stars.
                "method": "threshold",
                "threshold": 16,
                "maxval": 255,
                "type": cv2.THRESH_BINARY + cv2.THRESH_OTSU,
                "comment": "Apply adaptive threshold to boost remaining stars.",
            },  # /BoostStars
        },  # /UrbanFilter
    }  # /FILTERSCRIPTS

    def __init__(self, name=None, logger=None):
        """Create new image item.
        name = any arbitrary name for the image.
        width = pixel width.
        height = pixel height.
        depth = image depth (2 = Grayscale, 3 = BGR, 4 = BGRA)
        datatype = the storage type for each cell. default uint8 = unsigned 8 bit values.
        """
        self.name = name
        self.set_logger(logger)  # Any method which supports pilomar's .Log() methods.
        self.log_drawing = False  # Record individual drawing commands in the log file?
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.invert_height = False  # When set to TRUE, height pixel values are inverted, so they count UP FROM THE BOTTOM instead of DOWN FROM THE TOP.
        self._initialize()
        self.reset_graph()  # Create structures for graphing data.

    def orient_height(self, y, height=None):
        """If InvertHeight is TRUE, invert the value of the 'y' pixel locations.
        This is good to convert a single 'y' dimension.
        If you have a tuple of (x,y) values, use OrientCoord() instead.

        Only apply this to coordinates which are being passed directly to opencv function calls.
        If you apply it to higher level method calls in this class you may end up applying it twice which will cancel the effect out.
        """
        if (
            self.invert_height
        ):  # Co-ordinates provided are from BOTTOM UP, convert to TOP DOWN for OpenCV.
            if height is None:
                height = self.get_height()
            y = height - y  # Pixel locations count UP instead of DOWN.
        return int(y)

    def orient_coord(self, location, yloc=1, angle=0, height=None):
        """If InvertHeight is TRUE, this returns a coordinate pair with the height dimension inverted.
        yloc says which entry in the location pair is the height one.
        This converts tuples (x,y) and (y,x) style.
        If you have a single 'y' value, use OrientHeight(y) instead.
        If you specify angle: It's the rotation angle of the image (when using AddAngleText() for example. 90, 270 rotations orient along X axis instead.

        Only apply this to coordinates which are being passed directly to opencv function calls.
        If you apply it to higher level method calls in this class you may end up applying it twice which will cancel the effect out.
        """
        if yloc == 1:  # y location is at position 1 in the tuple, convert that.
            x = location[0]
            y = self.orient_height(location[1])
            r = (x, y)
        else:  # y location is at position 0 in the tuple, convert that.
            x = location[1]
            y = self.orient_height(location[0])
            r = (y, x)
        return r

    def reset_graph(self):
        """Create data structure for basic charting/graphing.
        This also clears any existing graphing data."""
        self.graph_data_sets = (
            []
        )  # DataPoint = [x,y,color,label,style] # DataSet = list of DataPoint # DataSets = list of DataSet
        self.graph_title = "title"
        self.graph_x_axis_title = "x axis"
        self.graph_y_axis_title = "y axis"
        self.graph_x_min_val = None  # Lowest X value in data points.
        self.graph_x_max_val = None  # Highest X value in data points.
        self.graph_y_min_val = None  # Lowest Y value in data points.
        self.graph_y_max_val = None  # Highest Y value in data points.
        self.graph_x_border = None  # Width of left/right border.
        self.graph_y_border = None  # Height of top/bottom border.
        self.graph_x_value_span = None  # Span of X values.
        self.graph_y_value_span = None  # Span of Y values.
        self.graph_x_ticks = None  # Value of X axis ticks.
        self.graph_y_ticks = None  # Value of Y axis ticks.

    def interpolate(self, inp1, res1, inp2, res2, inp3):
        """Linear interpolation from 2 points."""
        inpdelta = inp2 - inp1
        resdelta = res2 - res1
        if inpdelta != 0.0:  # Input points are different, so result can be calculated.
            res3 = ((inp3 - inp1) * float(resdelta / inpdelta)) + res1
        else:  # 2 input points are the same, result is unknown.
            res3 = res1  # Default to first result.
        return res3

    def map_to_graph(self, xpoint, ypoint):
        """Given an x/y pair, find the pixel locations on a graph image.
        xpoint and ypoint are the data values stored in the Datasets."""
        x = int(
            self.interpolate(
                self.graph_x_min_val,
                self.graph_x_border,
                self.graph_x_max_val,
                self.get_width() - self.graph_x_border,
                xpoint,
            )
        )  # Scale it to the size of the canvas.
        y = int(
            self.interpolate(
                self.graph_y_min_val,
                self.graph_y_border,
                self.graph_y_max_val,
                self.get_height() - self.graph_y_border,
                ypoint,
            )
        )  # Scale it to the size of the canvas.
        return x, y

    def draw_x_axis(self):
        """Draw X axis, scale and label"""
        # Draw X scale where Y = 0 or at min Y
        if self.graph_y_min_val < 0 and self.graph_y_max_val > 0:
            y = 0  # Where does x axis cross Y?
        elif self.graph_y_max_val < 0:
            y = self.graph_y_max_val
        else:
            y = self.graph_y_min_val
        x1, y1 = self.map_to_graph(self.graph_x_min_val, y)
        x2, y2 = self.map_to_graph(self.graph_x_max_val, y)
        self.draw_line(
            (x1, y1), (x2, y2), color=PilomarImage.BGRColor["Black"]
        )  # x-axis
        # Mark scale.
        i = self.graph_x_min_val
        while i <= self.graph_x_max_val:
            # Mark this location and value.
            x1, y1 = self.map_to_graph(i, y)
            y2 = y1 - 20
            self.draw_line(
                (x1, y1), (x1, y2), color=PilomarImage.BGRColor["Black"]
            )  # Tick mark.
            self.add_text(
                str(round(i, 3)),
                x1,
                y1 - 30,
                color=PilomarImage.BGRColor["Black"],
                hjust="c",
                vjust="t",
            )
            i += self.graph_x_ticks
        # Label the axis.
        cx, _ = self.center_coordinates()
        self.add_text(
            self.graph_x_axis_title,
            cx,
            int(self.graph_y_border / 2),
            color=PilomarImage.BGRColor["Black"],
            size=2.0,
            hjust="c",
            vjust="c",
            thickness=2,
        )
        return True

    def draw_y_axis(self):
        """Draw X axis, scale and label"""
        # Draw Y scale where X = 0 or at min X
        if self.graph_x_min_val < 0 and self.graph_x_max_val > 0:
            x = 0  # Where does Y axis cross X?
        elif self.graph_x_max_val < 0:
            x = self.graph_x_max_val
        else:
            x = self.graph_x_min_val
        x1, y1 = self.map_to_graph(x, self.graph_y_min_val)
        x2, y2 = self.map_to_graph(x, self.graph_y_max_val)
        self.draw_line(
            (x1, y1), (x2, y2), color=PilomarImage.BGRColor["Black"]
        )  # y-axis
        # Mark scale.
        i = self.graph_y_min_val
        while i <= self.graph_y_max_val:
            # Mark this location and value.
            x1, y1 = self.map_to_graph(x, i)
            x2 = x1 - 20
            self.draw_line(
                (x1, y1), (x2, y1), color=PilomarImage.BGRColor["Black"]
            )  # Tick mark.
            self.add_text(
                str(round(i, 3)),
                x1 - 30,
                y1,
                color=PilomarImage.BGRColor["Black"],
                hjust="r",
                vjust="c",
            )
            i += self.graph_y_ticks
        # Label the axis.
        _, cy = self.center_coordinates()
        self.add_angle_text(
            self.graph_y_axis_title,
            int(self.graph_x_border / 2),
            cy,
            color=PilomarImage.BGRColor["Black"],
            size=2.0,
            hjust="c",
            vjust="c",
            thickness=2,
            angle=90,
        )  # Rotated. Not working smoothly yet.
        return True

    def list_data_sets(self):
        """Generate a key on the graph.
        List the names of the available data sets in the image."""
        x = self.get_width() - self.graph_x_border + 50
        self.add_text(
            "Datasets:-",
            x,
            self.get_height() - 500,
            color=PilomarImage.BGRColor["Black"],
        )
        for dataset in self.graph_data_sets:
            self.add_text(dataset.Name, x, self.prev_text_y, color=dataset.Color)
        return True

    def adddata_point(
        self,
        name,
        x,
        y,
        color=None,
        label=None,
        style=["dot"],
        xname=None,
        yname=None,
        xtolerance=0,
        ytolerance=0,
    ):
        """Find/add dataset and add this to it.
        color is specific to this single datapoint. Dataset color is used otherwise.
        xtolerance/ytolerance: point is not added if x,y is closer than this to the previous one.
        """
        # Check that the named dataset exists.
        foundit = False
        for dataset in self.graph_data_sets:
            if dataset.Name == name:
                foundit = True
        if foundit == False:  # Dataset does not exist yet, add it.
            dataset = DataSet(name)
            self.graph_data_sets.append(dataset)
        # Check for tolerance limits. Don't add if too close to last entry.
        oktoadd = True
        if xtolerance != 0 or ytolerance != 0:
            for dataset in self.graph_data_sets:
                if dataset.Name == name:
                    datapointcount = len(dataset.DataPoints)
                    if datapointcount > 0:
                        datapoint = dataset.DataPoints[-1]  # Get last point.
                        if (
                            abs(datapoint.X - x) < xtolerance
                            and abs(datapoint.Y - y) < ytolerance
                        ):
                            oktoadd = False  # New point is too close to old point. Don't add it.
        if oktoadd:  # Datapoint is OK to add.
            for dataset in self.graph_data_sets:
                if dataset.Name == name:
                    if color is None:
                        color = dataset.Color  # Inherit color from parent dataset.
                    datapoint = data_point(x, y, color, label, style, xname, yname)
                    dataset.Add(datapoint)
        return True

    def adddata_set(self, name, color=None, style=["line"]):
        """Create new dataset."""
        foundit = False
        for dataset in self.graph_data_sets:
            if dataset.Name == name:
                foundit = True
        if foundit == False:  # Dataset does not exist yet, add it.
            dataset = DataSet(name, color, style)
            self.graph_data_sets.append(dataset)
        result = not foundit
        return result

    def analyse_data_points(self):
        # Go through the graph datapoints and extract limits.
        self.graph_x_min_val = self.graph_x_max_val = self.graph_y_min_val = (
            self.graph_y_max_val
        ) = None
        if len(self.graph_data_sets) > 0:  # There are datasets to handle.
            for (
                dataset
            ) in (
                self.graph_data_sets
            ):  # Data point = [x,y,color,label,style] # DataSet = list of DataPoints, # DataSets = list of DataSets
                if len(dataset.DataPoints) > 0:  # There are datapoints to handle.
                    for point in dataset.DataPoints:  # Check each point.
                        if (
                            self.graph_x_min_val is None
                            or self.graph_x_min_val > point.X
                        ):
                            self.graph_x_min_val = point.X
                        if (
                            self.graph_y_min_val is None
                            or self.graph_y_min_val > point.Y
                        ):
                            self.graph_y_min_val = point.Y
                        if (
                            self.graph_x_max_val is None
                            or self.graph_x_max_val < point.X
                        ):
                            self.graph_x_max_val = point.X
                        if (
                            self.graph_y_max_val is None
                            or self.graph_y_max_val < point.Y
                        ):
                            self.graph_y_max_val = point.Y
        if self.graph_x_min_val is None:  # No values were found.
            self.graph_x_min_val = -1
            self.graph_x_max_val = 1
            self.graph_y_min_val = -1
            self.graph_y_max_val = 1
        # Check that each axis does span at least a small distance.
        if self.graph_x_min_val == self.graph_x_max_val:
            self.graph_x_min_val -= 1
            self.graph_x_max_val += 1
        if self.graph_y_min_val == self.graph_y_max_val:
            self.graph_y_min_val -= 1
            self.graph_y_max_val += 1
        return True

    def establish_graph_scale(self):
        """What scale to use on each axis.
        Where to place tickmarks on each axis."""
        self.graph_x_value_span = self.graph_x_max_val - self.graph_x_min_val
        self.graph_y_value_span = self.graph_y_max_val - self.graph_y_min_val
        self.graph_x_ticks = self.graph_x_value_span / 10
        self.graph_y_ticks = self.graph_y_value_span / 10
        return True

    def plot_data(self):
        """Plot the actual data points on the graph.

        self.x = x
        self.y = y
        self.color = color
        self.label = label
        self.style = Style
        self.x_name = xname
        self.y_name = yname
        """
        for dataset in self.graph_data_sets:
            prevx = None
            prevy = None
            for i, datapoint in enumerate(dataset.DataPoints):
                x, y = self.map_to_graph(datapoint.X, datapoint.Y)
                r = 5
                color = self.safe_color(
                    datapoint.Color, default=PilomarImage.BGRColor["Fuchsia"]
                )
                if "line" in dataset.Style and i > 0:  # Line between points.
                    self.draw_line(
                        (prevx, prevy),
                        (x, y),
                        color=self.safe_color(
                            dataset.Color, default=PilomarImage.BGRColor["Cyan"]
                        ),
                    )
                if "dot" in datapoint.Style:  # Draw a small dot where the datapoint is.
                    self.fill_circle(x, y, r, color)  # Dot on the datapoint.
                if (
                    "point" in datapoint.Style
                ):  # Draw a single pixel where the datapoint is.
                    self.set_pixel(x, y, color)  # Single pixel at the datapoint.
                prevx = x
                prevy = y
        return True

    def export_data(self, filename):
        """Dump the graph data."""
        ft = filename.rindex(".")
        filename = filename[:ft] + ".dat"
        self.log(
            "pilomarimage", self.name, ".ExportData:", str(filename), terminal=False
        )
        with open(filename, "w") as f:
            line = "dataset.Name\t"
            line += "datapoint.X\t"
            line += "datapoint.Y\t"
            line += "datapoint.Label\t"
            line += "datapoint.XName\t"
            line += "datapoint.YName\t"
            line += "\n"
            f.write(line)
            for dataset in self.graph_data_sets:
                for datapoint in dataset.DataPoints:
                    line = str(dataset.Name) + "\t"
                    line += str(datapoint.X) + "\t"
                    line += str(datapoint.Y) + "\t"
                    line += str(datapoint.Label) + "\t"
                    line += str(datapoint.XName) + "\t"
                    line += str(datapoint.YName) + "\t"
                    line += "\n"
                    f.write(line)
        return True

    def plot_graph(self, height, width, filename, export=False):
        """Create very simplistic graph.
        If height/width not given, the current buffer is used.
        This is VERY crude! IF you want proper graphing capabilities then install matplotlib!
        This is really to support development/debugging work sometimes while avoiding having to install extra packages.
        export=True means a datafile is dumped too."""
        self.log(
            "pilomarimage",
            self.name,
            ".PlotGraph:",
            str(filename),
            str(export),
            terminal=False,
        )
        self.invert_height = (
            True  # Easier to plot graphs if HEIGHT pixels count from the bottom up.
        )
        # Find axis limits.
        self.analyse_data_points()
        # Establish scale
        self.establish_graph_scale()
        # Establish graph space
        self.new(height, width, "bgr")  # New BGR image.
        self.fill_color(PilomarImage.BGRColor["White"])  # White canvas
        self.graph_x_border = int(width * 0.1)
        self.graph_y_border = int(height * 0.1)
        self.draw_rectangle(
            (self.graph_x_border, self.graph_y_border),
            (width - self.graph_x_border, height - self.graph_y_border),
            color=PilomarImage.BGRColor["DarkGray"],
        )
        self.draw_x_axis()  # Draw X axis on graph.
        self.draw_y_axis()  # Draw Y axis on graph.
        x, y = self.center_coordinates()
        self.add_text(
            self.graph_title,
            x,
            int(height - self.graph_y_border / 2),
            size=3,
            color=PilomarImage.BGRColor["Black"],
            thickness=3,
            hjust="c",
            vjust="c",
        )
        self.list_data_sets()  # Add labels for the available datasets.
        self.plot_data()  # Plot the data on the graph.
        self.draw_graph_id()  # Write footing information onto the graph.
        # Save the result.
        self.save_file(filename)
        if export:
            self.export_data(filename)  # Export the data.
        self.invert_height = (
            False  # Revert to counting height locations from the top down.
        )
        return True

    def draw_graph_id(self):
        """Write footing information onto the graph."""
        line = " pilomarimage.PlotGraph " + str(datetime.now()).split(".")[0] + " UTC "
        self.add_text(
            line,
            self.get_width() - 10,
            20,
            color=PilomarImage.BGRColor["Black"],
            hjust="r",
        )
        return True

    def set_logger(self, logger):
        """Set up link to logging class and shortcuts to common methods."""
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.logger = logger  # Logger instance.
        self.log = self._null_logger  # No log method.
        self.report_exception = (
            self._null_logger
        )  # Cannot report exception details to logfile.
        self.raise_exception = self._null_logger  # Cannor report and raise exception.
        if hasattr(logger, "Log"):
            self.log = logger.Log  # Log method.
        if hasattr(logger, "ReportException"):
            self.report_exception = (
                logger.ReportException
            )  # Report exception details to logfile.
        if hasattr(logger, "RaiseException"):
            self.raise_exception = logger.RaiseException  # Report and raise exception.
        # self.log("pilomarimage.SetLogger: Linked to this log file.",terminal=False)

    def _null_logger(self, *args, **kwargs):
        """Null logger. Absorbs parameters and .log call but does nothing.
        Use this when there is no logger defined."""
        return

    def _initialize(self):
        """Create default values for the object.
        This creates initial values for new instances, and also clears them out if you want to reset an existing one.
        """
        self.image_buffer = None  # This is the actual OpenCV / Numpy image buffer.
        self.image_mask = (
            None  # Array identifying which cells are occupied and which to ignore.
        )
        self.image_accumulator = (
            None  # Array of cumulative image values. (For live stacking)
        )
        self.image_counter = None  # Array of how many values are accumulated into each pixel of self.image_accumulator. (For live stacking)
        self.action_list = []  # List of actions performed on the image.
        self.created_timestamp = self.now_utc()
        self.modified_timestamp = None
        self.star_list = []  # Was None
        self.star_count = 0
        self.star_match_list = None
        self.horizontal_spread = 0  # % of horizonal spread of stars.
        self.vertical_spread = 0  # % of vertical spread of stars.
        self.area_spread = 0  # % of area spread of stars.
        self.pen_color = None  # Default color for drawing.
        self.pen_thickness = 1  # Default pen thickness for drawing.
        self.line_type = cv2.LINE_AA  # Default line_type for drawing.
        self.resize_method = (
            cv2.INTER_AREA
        )  # Which sampling method is used for resizing? (3)
        self.resize_methods = [
            cv2.INTER_NEAREST,  # nearest neighbor interpolation technique (0)
            cv2.INTER_LINEAR,  # bilinear interpolation (default) (1)
            cv2.INTER_AREA,  # resampling using pixel area relation (3)
            cv2.INTER_CUBIC,  # bicubic interpolation over 4 x 4 pixel neighborhood (2)
            cv2.INTER_LANCZOS4,
        ]  # Lanczos interpolation over 8 x 8 pixel neighborhood (4)
        # cv2.INTER_LINEAR_EXACT, cv2.INTER_NEAREST_EXACT, cv2.INTER_MAX, cv2.WARP_FILL_OUTLIERS, cv2.WARP_INVERSE_MAP] # (16) Not in this version.
        self.next_text_y = None  # When text is printed, this holds the 'y' position of the next line of text if you want to print a block of text.
        self.next_text_x = None  # When text is printed, this holds the 'x' position of the next line of text if you want to print a block of text.
        self.prev_text_y = None  # When text is printed, this holds the 'y' position of the next line of text if you want to print a block of text going UPWARDS.
        self.prev_text_x = None  # When text is printed, this holds the 'x' position of the next line of text if you want to print a block of text goind UPWARDS.
        # Text collision avoidance...
        self.text_list = (
            []
        )  # When text is printed, this holds the co-ordinates of each block of text added [[fromx,fromy,tox,toy],[fromx,fromy,tox,toy],[fromx,fromy,tox,toy],...]
        self.avoid_text_collisions = False  # When TRUE, new text is only created if it doesn't overlap existing text.
        self.exif_data = (
            {}
        )  # Empty dictionary of any associated EXIF tags loaded from an image.

    def text_collision(self, fromx, fromy, tox, toy):
        """Return TRUE if proposed text area collides with an existing one."""
        result = False
        if self.avoid_text_collisions:  # Collision avoidance is active.
            fromx, tox = min(fromx, tox), max(
                fromx, tox
            )  # Make sure FROM is less than TO
            fromy, toy = min(fromy, toy), max(fromy, toy)
            for items in self.text_list:  # Go through existing text items.
                ifx = items[0]  # Pull co-ordinates.
                ify = items[1]
                itx = items[2]
                ity = items[3]
                if tox < ifx or fromx > itx or toy < ify or fromy > ity:
                    # Right side of proposed text is < left side of existing text
                    # Left side of proposed text is > right side of existing text
                    # Top of proposed text is < bottom of existing text
                    # Bottom of proposed text is > top of existing text
                    pass  # No collision.
                else:  # Collision!
                    result = True
                    break
            if (
                not result
            ):  # Text does not collide, we'll at it to the list of allowed text.
                self.text_list.append([fromx, fromy, tox, toy])
        return result

    def calculate_star_spread(self):
        """Calculate an approximation for the % of the frame that contains stars.
        LOW values mean that the stars are not spread out evenly across the frame.
        HIGH values mean that the stars are spread out more evenly across the frame.
        Sets % value for each axis and the total image."""
        if (
            self.image_exists() and len(self.star_list) > 0
        ):  # There's an image loaded and stars were identified.
            HMin = None  # Lowest 'X' position of a star.
            HMax = None  # Highest 'X' position of a star.
            VMin = None  # Lowest 'Y' position of a star.
            VMax = None  # Highest 'Y' position of a star.
            for star in self.star_list:  # Each star is a list of [x, y, radius]
                if HMin is None or HMin > star[0]:
                    HMin = star[0]
                if HMax is None or HMax < star[0]:
                    HMax = star[0]
                if VMin is None or VMin > star[1]:
                    VMin = star[1]
                if VMax is None or VMax < star[1]:
                    VMax = star[1]
            self.horizontal_spread = 100 * (HMax - HMin) / self.get_width()
            self.vertical_spread = 100 * (VMax - VMin) / self.get_height()
            self.area_spread = 100 * (
                (self.horizontal_spread / 100) * (self.vertical_spread / 100)
            )
            result = True
        else:  # There's no image, or no stars were identified.
            self.horizontal_spread = self.vertical_spread = self.area_spread = (
                0  # No spread to measure.
            )
            result = False
        return result

    def next_interpolation(self):
        """Move on to the next available sampling method."""
        self.log("pilomarimage", self.name, ".NextInterpolation()", terminal=False)
        i = (self.resize_methods.index(self.resize_method) + 1) % len(
            self.resize_methods
        )
        self.resize_method = self.resize_methods[i]
        self.action_list.append(["nextinterpolation", self.resize_method])

    def prev_interpolation(self):
        """Move back to the previous available sampling method."""
        self.log("pilomarimage", self.name, ".PrevInterpolation()", terminal=False)
        i = (self.resize_methods.index(self.resize_method) - 1) % len(
            self.resize_methods
        )
        self.resize_method = self.resize_methods[i]
        self.action_list.append(["previnterpolation", self.resize_method])

    def now_utc(self):
        """Return system UTC timestamp."""
        return datetime.now(timezone.utc)

    def clear(self):
        """Clear the image buffer and related attributes."""
        self.log("pilomarimage", self.name, ".Clear()", terminal=False)
        self._initialize()
        self.action_list.append(["clear"])
        self.created_timestamp = self.now_utc()
        self.modified_timestamp = self.now_utc()

    def load_buffer(self, imagebuffer):
        """Import an existing OpenCV/Numpy image buffer."""
        self.log("pilomarimage", self.name, ".load_buffer()", terminal=False)
        self.clear()
        if type(imagebuffer) != type(None):
            self.image_buffer = imagebuffer.copy()
            self.modified_timestamp = self.now_utc()
        else:
            self.log(
                "pilomarimage",
                self.name,
                ".load_buffer(). FROM buffer is None.",
                terminal=False,
            )
        return self.image_exists()

    def accumulate_buffer(self, buffer):
        """Accumulate values in a buffer into a running total buffer.
        buffer is a reference to another pilomarimage instance."""
        self.log("pilomarimage", self.name, ".AccumulateBuffer()", terminal=False)
        if isinstance(self.image_accumulator, type(None)):  # Initialize accumulator.
            self.image_accumulator = np.zeros_like(
                buffer.image_buffer, np.uint16
            )  # Create array of same dimensions, but with larger storage type.
            self.image_counter = np.zeros_like(
                buffer.image_buffer, np.uint8
            )  # Create array of same dimensions but with uint8 storage type.
        # Now accumulate the values.
        self.image_accumulator.add(self.image_accumulator, buffer.image_buffer)
        self.image_count += 1
        self.action_list.append(["accumulatebuffer", buffer.Name])
        self.modified_timestamp = self.now_utc()
        return True

    def resolve_accumulator(self):
        self.log("pilomarimage", self.name, ".ResolveAccumulator()", terminal=False)
        if isinstance(self.image_accumulator, type(None)):
            print(
                "pilomarimage.ResolveAccumulator(): ImageAccumulator is not initialised."
            )
            return False
        # Create fresh image buffer.
        self.image_buffer = np.zeros_like(
            self.image_accumulator, np.uint8
        )  # Create array of same dimensions, but with regular image datatype.
        self.image_buffer[self.image_count != 0] = (
            self.image_accumulator / self.image_count
        )
        self.action_list.append(["resolveaccumulator"])
        self.modified_timestamp = self.now_utc()
        return True

    def get_exif(self, filename):
        """Given a disc file, load any EXIF tags available.
        Returns a dictionary of TAG name and value.
        It does not populate self.exif_data dictionary."""
        # from PIL import Image as PIL_Image
        # from PIL import ExifTags as PIL_ExifTags
        with PIL_Image.open("img.jpg") as img:  # Use PIL to open the image.
            raw_data = (
                img.getexif()
            )  # Use PIL getexif() method to extract raw exif data.
        if raw_data is None:
            raw_data = {}  # No exif data available.
        for (
            key,
            val,
        ) in raw_data.items():  # Convert the raw exif keys into recognisable tags.
            if key in PIL_ExifTags:  # Can convert key into a tag.
                exif_data[PIL_ExifTags.TAGS[key]] = val
            else:  # Cannot convert the key.
                exif_data[key] = val
        return exif_data

    def load_file(self, filename, loadexif=False):
        """Load image buffer from disc."""
        self.log("pilomarimage", self.name, ".LoadFile(", filename, ")", terminal=False)
        self._initialize()
        self.image_buffer = cv2.imread(filename, cv2.IMREAD_COLOR)
        if self.image_exists():
            self.image_mask = np.ones_like(
                self.image_buffer, np.uint8
            )  # All cells are active.
            self.action_list.append(["load", filename])
            self.created_timestamp = self.now_utc()
            result = True
            if loadexif:  # Also load the EXIF tags from the file.
                self.exif_data = self.get_exif(filename)
            else:
                self.exif_data = {}  # Empty.
        else:
            # File didn't load!
            self.log(
                "pilomarimage",
                self.name,
                ".LoadFile(",
                filename,
                ") failed.",
                terminal=False,
            )
            result = False
        return result

    def image_file_type(self, filename):
        """Given a filename, return a lower case file type."""
        return filename.split(".")[-1].lower()

    def save_file(self, filename, quality=None):
        """Save image buffer to disc.
        To specify the quality for jpeg files you can use a call like this...
            cv2.imwrite(filename,self.image_buffer,[int(cv2.IMWRITE_JPEG_QUALITY), 90] # 90% image quality.
        Set the 'quality' input parameter when making this call to override the jpg quality to your preferred value.
        """
        self.log(
            "pilomarimage", self.name, ".save_file(", filename, ")", terminal=False
        )
        if self.image_exists():
            if quality is not None:  # Image quality was specified.
                cv2.imwrite(
                    filename,
                    self.image_buffer,
                    [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
                )  # imwrite doesn't report errors very well, beware.
            else:  # Image quality can be default.
                cv2.imwrite(
                    filename, self.image_buffer
                )  # imwrite doesn't report errors very well, beware.
            self.action_list.append(["save", filename])
        else:
            print("pilomarimage.save_file(", filename, "): No image_buffer.")
        height, width = self.get_dimensions()
        maxdim = max(
            height, width
        )  # Which is the largest dimension? Some file formats have limits.
        ift = self.image_file_type(filename)  # What file type are we generating?
        if ift in ["bmp"] and maxdim > 32768:  # bmp dimensions can't exceed this size.
            print(
                "pilomarimage.save_file(",
                filename,
                "): Image dimensions exceed bmp limits.(",
                height,
                width,
                ")",
            )
        elif (
            ift in ["jpg", "jpeg"] and maxdim > 65535
        ):  # jpeg dimensions can't exceed this size.
            print(
                "pilomarimage.save_file(",
                filename,
                "): Image dimensions exceed jpeg limits.(",
                height,
                width,
                ")",
            )
        # Check it worked. Big images fail silently!
        result = False  # Failed unless a file exists which contains something.
        if os.path.exists(filename):
            if os.path.getsize(filename) == 0:
                print(
                    "pilomarimage.save_file(",
                    filename,
                    "): The file exists but it is empty.",
                )
            else:
                result = True
        else:
            print("pilomarimage.save_file(", filename, "): The file was not saved.")
        return result

    def clip_image(self, xstart, ystart, xend, yend):
        """Clip the image."""
        self.log(
            "pilomarimage",
            self.name,
            ".ClipImage(",
            xstart,
            ystart,
            xend,
            yend,
            ")",
            terminal=False,
        )
        gt = self.get_type()
        if gt == "grayscale":
            self.image_buffer = self.image_buffer[ystart:yend, xstart:xend]
        else:
            self.image_buffer = self.image_buffer[ystart:yend, xstart:xend, :]
        self.action_list.append(["clip", xstart, ystart, xend, yend])
        self.modified_timestamp = self.now_utc()
        return True

    def scale_image(self, scale=None, vscale=None, hscale=None):
        """Scale the current image buffer by 'scale' ratio.
        scale is applied in both dimensions.
        vscale is applied to vertical only.
        hscale is applied to horizontal only."""
        self.log("pilomarimage", self.name, ".ScaleImage(", scale, ")", terminal=False)
        if scale is not None:  # Same scale in both directions.
            vscale = scale
            hscale = scale
        if vscale <= 0.0:
            print("pilomarimage.ScaleImage(vscale", vscale, ") must be > 0.0")
            return False
        if hscale <= 0.0:
            print("pilomarimage.ScaleImage(hscale", hscale, ") must be > 0.0")
            return False
        height = int(self.image_buffer.shape[0] * vscale)
        width = int(self.image_buffer.shape[1] * hscale)
        self.log(
            "pilomarimage",
            self.name,
            ".ScaleImage: Dimensions h",
            height,
            "w",
            width,
            terminal=False,
        )
        self.image_buffer = cv2.resize(
            self.image_buffer, (width, height), interpolation=self.resize_method
        )  # Note RESIZE takes (width,height) rather than usual openCV (height,width)!
        self.action_list.append(["scale", scale, vscale, hscale, (width, height)])
        self.modified_timestamp = self.now_utc()
        return True

    def horizontal_blur_image(self, band):
        """Shrink the current image buffer horizontally, averaging the colors.
        Then return the image buffer to the correct width, blurring that average across the image.
        band = the pixel width that the image is horizontally compressed to."""
        self.log(
            "pilomarimage",
            self.name,
            ".HorizontalBlurImage(",
            band,
            ")",
            terminal=False,
        )
        height = int(self.image_buffer.shape[0])
        originalwidth = int(self.image_buffer.shape[1])
        scale = band / originalwidth
        if scale <= 0.0:
            print("pilomarimage.HorizontalBlurImage(scale", scale, ") must be > 0.0")
            return False
        width = int(originalwidth * scale)
        self.log(
            "pilomarimage",
            self.name,
            ".HorizontalBlureImage: Dimensions h",
            height,
            "w",
            width,
            terminal=False,
        )
        self.image_buffer = cv2.resize(
            self.image_buffer, (width, height), interpolation=cv2.INTER_AREA
        )  # INTER_AREA better for SHRINKING.
        self.image_buffer = cv2.resize(
            self.image_buffer, (originalwidth, height), interpolation=cv2.INTER_LINEAR
        )  # INTER_LINEAR and INTER_CUBIC best for STRETCHING.
        self.action_list.append(["horizontalblurimage", scale, (width, height)])
        self.modified_timestamp = self.now_utc()
        return True

    def horizontal_blur_buffer(self, buffer, band):
        """Shrink the current image buffer horizontally, averaging the colors.
        Then return the image buffer to the correct width, blurring that average across the image.
        buffer = the image buffer to work on.
        band = the pixel width that the image is horizontally compressed to."""
        self.log(
            "pilomarimage",
            self.name,
            ".HorizontalBlurBuffer(",
            band,
            ")",
            terminal=False,
        )
        height = int(buffer.shape[0])
        originalwidth = int(buffer.shape[1])
        scale = band / originalwidth
        if scale <= 0.0:
            print("pilomarimage.HorizontalBlurBuffer(scale", scale, ") must be > 0.0")
            return False
        width = int(originalwidth * scale)
        self.log(
            "pilomarimage",
            self.name,
            ".HorizontalBlureImage: Dimensions h",
            height,
            "w",
            width,
            terminal=False,
        )
        buffer = cv2.resize(
            buffer, (width, height), interpolation=cv2.INTER_AREA
        )  # INTER_AREA better for SHRINKING.
        buffer = cv2.resize(
            buffer, (originalwidth, height), interpolation=cv2.INTER_LINEAR
        )  # INTER_LINEAR and INTER_CUBIC best for STRETCHING.
        self.action_list.append(["horizontalblurimage", scale, (width, height)])
        self.modified_timestamp = self.now_utc()
        return buffer

    def percentage_buffer(self, buffer, percentage):
        """Dim a buffer to input percentage.
        percentage = 0 : Buffer is fully black.
        percentage = 50 : Buffer is reduced by 50%.
        percentage = 100 : Buffer is returned unchanged."""
        self.log("pilomarimage", self.name, ".PercentageBuffer()", terminal=False)
        pc = percentage / 100
        buffer = cv2.multiply(buffer, (pc, pc, pc, 1.0))
        return buffer

    def subtract_buffer(self, buffer):
        """Subtract 'buffer' from the main image buffer."""
        self.log("pilomarimage", self.name, ".SubtractBuffer()", terminal=False)
        self.image_buffer = cv2.subtract(self.image_buffer, buffer)
        self.action_list.append(["subtractbuffer"])
        self.modified_timestamp = self.now_utc()
        return True

    def clone_image(self, donor):
        """Make this a copy of some other buffer.
        donor is a reference to another pilomarimage instance."""
        self.log(
            "pilomarimage", self.name, ".CloneImage(", donor.Name, ")", terminal=False
        )
        if isinstance(donor.image_buffer, type(None)):
            self.image_buffer = None
        else:
            self.image_buffer = donor.image_buffer.copy()
        if isinstance(donor.ImageMask, type(None)):
            self.image_mask = None
        else:
            self.image_mask = donor.ImageMask.copy()
        if isinstance(donor.ImageAccumulator, type(None)):
            self.image_accumulator = None
        else:
            self.image_accumulator = donor.ImageAccumulator.copy()
        if isinstance(donor.ImageCounter, type(None)):
            self.image_counter = None
        else:
            self.image_counter = donor.ImageCounter.copy()
        self.action_list = []
        self.created_timestamp = self.created_timestamp
        self.modified_timestamp = donor.ModifiedTimestamp
        self.star_list = donor.StarList
        self.star_count = donor.StarCount
        self.action_list.append(["cloneimage", donor.Name])
        return self.image_exists()

    def sharpness(self):
        """Assess the crispness of an image.
        Some images will be sharper than others.
        *Q* UNDER DEVELOPMENT!
        This is a solution found online ....
        https://stackoverflow.com/questions/28717054/calculating-sharpness-of-an-image (Vektorsoft)
        low return values = More blurred.
        high return values = More crisp."""
        self.log("pilomarimage", self.name, ".Sharpness()", terminal=False)
        canny = cv2.Canny(
            self.new_buffer_type("grayscale"), 50, 250
        )  # Use canny edge detection.
        sharpness = np.mean(canny)
        return sharpness

    def combine_image(self, donor):
        """Add donor image to this image.
        Performs simple addition of the two images.
        Values clipped between 0 and 255 though."""
        tempimage = self.image_buffer.copy().astype(np.uint16)
        tempimage = np.add(tempimage, donor)
        tempimage = np.clip(tempimage, 0, 255).astype(np.uint8)  # Clip to uint8 values.
        self.image_buffer = tempimage
        self.action_list.append(["combineimage", donor.Name])
        self.modified_timestamp = self.now_utc()
        return True

    def merge_layer(self, donor):
        """Merge a donor image as a new layer on top of the current buffer.
        *Q* UNDER DEVELOPMENT!
        Several ways to perform a merge. This is testing a couple of them.
        Likely to change in the future."""
        self.log(
            "pilomarimage", self.name, ".MergeLayer(", donor.Name, ")", terminal=False
        )
        gt = self.get_type()
        if gt == "grayscale":  # Grayscale images inherit the average of the two arrays.
            self.image_buffer = ((self.image_buffer + donor.image_buffer) / 2).astype(
                np.uint8
            )
        elif gt == "bgr":  # BGR images inherit average of the two arrays.
            self.image_buffer = ((self.image_buffer + donor.image_buffer) / 2).astype(
                np.uint8
            )
        else:  # BGRA can use the 'A' channel to decide how much to inherit.
            b1 = (
                self.image_buffer.copy().astype(np.float16) / 255
            )  # Scale everything 0.0 - 1.0
            b2 = donor.image_buffer.copy.astype(np.float16) / 255
            alpha = b2[:, :, 3]  # Extract alpha channel.
            b1[:, :, :3] = b1 * (
                1 - alpha
            )  # Apply alpha to BGR channels (All X, All Y and 0,1,2 channels. Not Alpha channel (3).
            b2[:, :, :3] = b2 * alpha
            self.image_buffer = np.add(b1, b2)  # Add two arrays.
            self.image_buffer = self.image_buffer * 255  # Scale back up to 0-255
            self.image_buffer = self.image_buffer.astype(
                np.uint8
            )  # Convert from float back to uint8
        self.action_list.append(["mergelayer", donor.Name])
        self.modified_timestamp = self.now_utc()

    def center_coordinates(self):
        """Return current center of the image."""
        x = int(round(self.get_width() / 2, 0))
        y = int(round(self.get_height() / 2, 0))
        return x, y

    def rotate_coordinates(self, x, y, angle):
        """Transpose coordinates to account for image rotating.
        Only supports 0,90,180,270 rotations at the moment."""
        angle = angle % 360  # Convert to 0-359 degrees.
        if angle == 270:
            newx = y
            newy = self.get_height() - x
        elif angle == 180:
            newx = self.get_width() - x
            newy = self.get_height() - y
        elif angle == 90:
            newx = self.get_width() - y
            newy = x
        else:  # Angle = 0, which means don't rotate anything.
            newx = x
            newy = y
        return newx, newy

    def center_vector_to_pixel(self, PixDist, PixAngle):
        """Given ANGLE and PIXEL DISTANCE from current centre of image, return the resulting point."""
        FromX, FromY = self.center_coordinates()
        ToX, ToY = self.vector_to_pixel(FromX, FromY, PixDist, PixAngle)
        return ToX, ToY

    def vector_to_pixel(self, FromX, FromY, PixDist, PixAngle):  # 0 references.
        """Given ANGLE and PIXEL DISTANCE from 1 point, return the resulting point."""
        rad = math.radians(PixAngle)
        ToX = int(FromX + PixDist * math.sin(rad))
        ToY = int(FromY - PixDist * math.cos(rad))  # Y is inverted.
        return ToX, ToY

    def calculate_vector(self, FromX, FromY, ToX, ToY):  # 4 references.
        """Return ANGLE and PIXEL DISTANCE from 1 point to another."""
        XDist = ToX - FromX
        YDist = FromY - ToY  # Y values are inverted Y=0 at top.
        PixDist = round(math.sqrt((XDist**2) + (YDist**2)), 0)
        PixAngle = round(math.degrees(math.atan2(XDist, YDist)), 0)
        return PixDist, PixAngle

    def rotate_about_center(self, x, y, angle):
        """Take any point in the image and rotate it about the center of the image."""
        pixd, pixa = self.pixel_to_center_vector(x, y)
        pixa += angle
        cx, cy = self.center_coordinates()
        x, y = self.vector_to_pixel(cx, cy, pixd, pixa)
        return x, y

    def pixel_to_center_vector(self, ToX, ToY):  # 0 references.
        """Given any pixel location in an image, return its vector relative to the center of the image.
        Image UP (Y=0) is 0 Degrees.
        Image RIGHT (X=Max) is 90 Degrees.
        Image DOWN (Y=Max) is 180 Degrees.
        Image LEFT (X=0) is 270 Degrees."""
        cx, cy = self.center_coordinates()
        PixDist, PixAngle = self.calculate_vector(cx, cy, ToX, ToY)
        return PixDist, PixAngle

    def contains_meteors(self):
        """Return TRUE if meteors or aircraft trails are detected in an image."""
        if len(self.line_detection()) > 0:
            return True
        else:
            return False

    def line_detection(self) -> list:
        """Detect lines (satellites, meteors)."""
        self.log("pilomarimage", self.name, ".LineDetection()", terminal=False)
        # Code based upon https://www.meteornews.net/2020/05/05/d64-nl-meteor-detecting-project/
        # Make a gray-scale copy and save the result in the variable 'gray'
        gray = self.new_buffer_type("grayscale")
        # Apply blur and save the result in the variable 'blur'
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        # Apply the Canny edge algorithm
        canny = cv2.Canny(blur, 100, 200, 3)
        # The Hough line detection algorithm.
        lines = cv2.HoughLinesP(
            canny, 1, np.pi / 180, 25, minLineLength=50, maxLineGap=5
        )
        linereturn = []  # The list of selected lines that will be returned.
        longest = 0  # Length of longest line.
        if type(lines) != type(None):  # We have something to process.
            for i, line in enumerate(lines):  # Check each detected line in turn.
                x1, y1, x2, y2 = line[0]  # Coordinates of each end of the line.
                length = math.sqrt(
                    (x2 - x1) ** 2 + (y2 - y1) ** 2
                )  # Length of the line.
                if length < 10:
                    continue  # Too short.
                self.log(
                    "pilomarimage",
                    self.name,
                    ".LineDetection: Line",
                    i,
                    ",",
                    line[0],
                    ", length",
                    length,
                    terminal=False,
                )
                longest = max(length, longest)  # Is this the longest line found so far?
                linereturn.append(
                    [x1, y1, x2, y2]
                )  # Add to the list of detected lines.
        return linereturn

    def cloud_detection(self, threshold=127):  # In pilomarimage
        """Detect clouds in image.
        *Q* UNDER DEVELOPMENT
        threshold = minimum brightness at which a pixel could be a cloud."""
        cloudlist = []
        mincloudpixels = 400
        # Simplify image
        # - Grayscale
        imagebuffer = self.new_buffer_type("grayscale")  # Convert to grayscale.
        cv2.imwrite("/home/pi/pilomar/data/CloudDetectionGrayscale.jpg", imagebuffer)
        # - Blur
        imagebuffer = cv2.GaussianBlur(imagebuffer, (5, 5), 0)
        cv2.imwrite("/home/pi/pilomar/data/CloudDetectionBlurred.jpg", imagebuffer)
        # - Threshold
        ret, imagebuffer = cv2.threshold(imagebuffer, threshold, 255, 0)
        cv2.imwrite("/home/pi/pilomar/data/CloudDetectionThreshold.jpg", imagebuffer)
        # Analyse image
        contours = cv2.findContours(imagebuffer, 1, 2)
        for contour in contours:
            moments = cv2.moments(contour)
            center_x = int(moments["m10"] / moments["m00"])
            center_y = int(moments["m01"] / moments["m00"])
            area = int(moments["m00"])  # Contour area.
            if area > mincloudpixels:
                cloudlist.append([center_x, center_y, area])
                self.log(
                    "pilomarimage",
                    self.name,
                    ".CloudDetection (",
                    center_x,
                    ",",
                    center_y,
                    ")",
                    area,
                    "pixels",
                    terminal=False,
                )
        return cloudlist

    def get_type(self):
        """Are we dealing with grayscale, bgr or bgra image?"""
        result = None
        if isinstance(self.image_buffer, type(None)):
            result = None
        elif len(self.image_buffer.shape) < 3:
            result = "grayscale"
        elif self.image_buffer.shape[2] == 3:
            result = "bgr"
        elif self.image_buffer.shape[2] == 4:
            result = "bgra"
        return result

    def image_age(self):
        """Return age of the image buffer in seconds."""
        td = None
        if self.created_timestamp is not None:
            td = int((self.now_utc() - self.created_timestamp).total_seconds())
        return td

    def new_buffer_type(self, newtype):
        """Turn current image_buffer into a new type, but return as new buffer,
        doesn't overwrite the original image buffer."""
        cvimagebuffer = self.image_buffer.copy()
        if not newtype in PilomarImage.IMAGETYPES:
            self.log(
                "pilomarimage",
                self.name,
                ".ChangeType(",
                newtype,
                ") must be in ",
                PilomarImage.IMAGETYPES,
                terminal=False,
            )
            return cvimagebuffer
        oldtype = self.get_type()
        if oldtype == "bgra":
            if newtype == "bgr":
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGRA2BGR)
            elif newtype == "grayscale":
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGRA2GRAY)
        elif oldtype == "bgr":
            if newtype == "bgra":
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2BGRA)
            elif newtype == "grayscale":
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2GRAY)
        elif oldtype == "grayscale":
            if newtype == "bgr":
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_GRAY2BGR)
            elif newtype == "bgra":
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_GRAY2BGRA)
        checktype = None
        if type(cvimagebuffer) == type(None):
            checktype = None
        elif len(cvimagebuffer.shape) < 3:
            checktype = "grayscale"
        elif cvimagebuffer.shape[2] == 3:
            checktype = "bgr"
        elif cvimagebuffer.shape[2] == 4:
            checktype = "bgra"
        if checktype != newtype:
            self.log(
                "pilomarimage",
                self.name,
                ".ChangeType: Failed. From",
                oldtype,
                "to",
                newtype,
                "Found",
                checktype,
                terminal=False,
            )
        return cvimagebuffer

    def change_type(self, newtype):
        """Change image_buffer type."""
        self.image_buffer = self.new_buffer_type(newtype)
        self.image_mask = np.ones_like(self.image_buffer, np.uint8)
        self.action_list.append(["changetype", self.get_type()])
        return True

    def get_height(self):
        """Return the image_buffer height in pixels."""
        return self.image_buffer.shape[0]

    def get_width(self):
        """Return the image_buffer width in pixels."""
        return self.image_buffer.shape[1]

    def get_depth(self):
        """Return the image_buffer depth in pixels."""
        if len(self.image_buffer.shape) < 3:  # Grayscale
            depth = 1
        else:
            depth = self.image_buffer.shape[2]  # BGR = 3 or BGRA = 4
        return depth

    def get_dimensions(self):
        """Return the image_buffer dimensions in pixels."""
        return (self.get_height(), self.get_width())

    def get_pixel_color(self, y, x):
        """Return color of pixel.
        y = row
        x = column
        Converts datatype to int()"""
        tg = self.get_type()
        try:
            if tg == "grayscale":
                color = (
                    int(self.image_buffer[y, x]),
                    int(self.image_buffer[y, x]),
                    int(self.image_buffer[y, x]),
                )
            else:
                color = (
                    int(self.image_buffer[y, x, 0]),
                    int(self.image_buffer[y, x, 1]),
                    int(self.image_buffer[y, x, 2]),
                )
        except Exception as e:
            self.log(
                "pilomarimage.GetPixelColor(",
                self.name,
                ",row",
                y,
                ",col",
                x,
                ") failed.",
                terminal=False,
            )
            self.report_exception(e, comment="pilomarimage.GetPixelColor()")
            color = (0, 0, 0)
        return color

    def new(self, height, width, imagetype="bgr", datatype=np.uint8):
        """Create a new empty image_buffer."""
        self.log(
            "pilomarimage",
            self.name,
            ".New(",
            height,
            width,
            imagetype,
            datatype,
            ")",
            terminal=False,
        )
        if not imagetype in PilomarImage.IMAGETYPES:
            self.log(
                "pilomarimage",
                self.name,
                ".New(",
                imagetype,
                ") must be in ",
                PilomarImage.IMAGETYPES,
                terminal=False,
            )
            print(
                "pilomarimage",
                self.name,
                ".New(",
                imagetype,
                ") must be in ",
                PilomarImage.IMAGETYPES,
            )
            return False
        if max(height, width) > 65535:  # Maximum jpeg size.
            self.log(
                "pilomarimage: Dimensions exceed jpeg limits (",
                height,
                width,
                ").",
                terminal=False,
            )
        if imagetype == "bgr":
            self.image_buffer = np.zeros((height, width, 3), datatype)  # bgr image.
        elif imagetype == "bgra":
            self.image_buffer = np.zeros((height, width, 4), datatype)  # bgra image.
        else:
            self.image_buffer = np.zeros((height, width), datatype)  # grayscale image.
        self.image_mask = np.ones_like(self.image_buffer, np.uint8)
        self.created_timestamp = self.now_utc()
        self.modified_timestamp = self.now_utc()
        self.exif_data = (
            {}
        )  # Empty dictionary of any associated EXIF tags loaded from an image.
        self.action_list = [["new", (height, width), imagetype, datatype]]
        return True

    def arrange_objects(
        self,
        positions,
        objects,
        attractions,
        k=0.1,
        dt=0.1,
        iterations=100,
        delta_min=4.0,
    ):
        """
        Arrange Objects on an image using basic physics model (attractive and repulsive forces).
        This is a force directed model for distributing objects, it only avoids overlaps, it doesn't equally space items out.

        :param positions: List of [x, y] initial positions of the Objects. [[x,y],...]
        :param objects: List of object sizes as [[width, height , fixed],...]
            : width: pixel width of object.
            : height: pixel height of object.
            : fixed: boolean to say this object cannot move.
        :param attractions: List of objects which are attracted to each other [[obj1, obj2],...].
        :param k: Repulsive constant
        :param dt: Time step for simulation
        :param iterations: Sets limit on time spent finding a solution.
        :param delta_min: When the largest movement in an iteration falls below this number of pixels, the loop terminates.
        :return: List of new object positions as [[x, y],...]

        """
        # The basis of this code was generated by Bing ChatGPT Sep.2023.
        width = self.get_width()
        height = self.get_height()

        # Initialize label positions at the object positions
        object_positions = np.array(positions, dtype=np.float)

        # Iteratively apply forces to the object list until the locations stabilise.
        for m in range(iterations):  # Set limit to processing.

            # Note the positions at the start of the iteration.
            previous_positions = object_positions.copy()

            # Compute the force matrix between all pairs of objects
            forces = np.zeros_like(object_positions)

            # Calculate repulsive forces between objects.
            for i in range(len(objects)):
                for j in range(i + 1, len(objects)):
                    # Compute the overlap between objects i and j
                    object_i = objects[i]  # Retrieve object attributes.
                    object_j = objects[j]
                    object_i_fixed = object_i[2]  # Can the object move?
                    object_j_fixed = object_j[2]  # Can the object move?
                    overlap_x = max(
                        0,
                        (object_i[0] + object_j[0]) / 2
                        - abs(object_positions[i][0] - object_positions[j][0]),
                    )
                    overlap_y = max(
                        0,
                        (object_i[1] + object_j[1]) / 2
                        - abs(object_positions[i][1] - object_positions[j][1]),
                    )

                    # If there is an overlap, apply a repelling force
                    if overlap_x > 0 and overlap_y > 0:
                        direction = (
                            object_positions[i] - object_positions[j]
                        )  # Subtract [j] positions from [i] positions.
                        direction /= np.linalg.norm(
                            direction
                        )  # Convert to -1.0 <> 1.0 direction (array of (x,y) still).
                        force = (
                            direction * overlap_x * overlap_y * k
                        )  # Apply force to both axes (x,y).
                        if object_i_fixed == False:
                            forces[i] += force  # Apply force if object can move.
                        if object_j_fixed == False:
                            forces[j] -= force  # Apply force if object can move.

            # Apply a spring force between any attracted objects.
            for i in range(len(attractions)):  # Go through the list of attractions.
                index_a = attractions[i][
                    0
                ]  # Find the two objects being attracted to each other.
                index_b = attractions[i][1]
                object_a = objects[index_a]  # Get the object attributes.
                object_b = objects[index_b]
                position_a = object_positions[index_a]  # Get the object positions.
                position_b = object_positions[index_b]
                object_a_fixed = object_a[2]  # Can the object move?
                object_b_fixed = object_b[2]  # Can the object move?
                displacement = position_a - position_b
                dk = displacement * k
                if object_a_fixed == False:
                    forces[index_a] = forces[index_a] - dk  # Apply attraction forces.
                if object_b_fixed == False:
                    forces[index_b] = forces[index_b] + dk

            # Update the label positions using the computed forces
            fd = forces * dt
            object_positions = object_positions + fd

            # Keep the objects within the image bounds
            for i in range(len(objects)):
                object_positions[i][0] = min(
                    max(object_positions[i][0], objects[i][0] / 2),
                    width - objects[i][0] / 2,
                )
                object_positions[i][1] = min(
                    max(object_positions[i][1], objects[i][1] / 2),
                    height - objects[i][1] / 2,
                )

            delta = 0  # What's the largest move detected after this iteration?
            for i, origpos in enumerate(
                previous_positions
            ):  # Check how far each object has moved in this iteration.
                newpos = object_positions[i]
                move = (
                    ((newpos[0] - origpos[0]) ** 2) + ((newpos[1] - origpos[1]) ** 2)
                ) ** 0.5
                delta = max(move, delta)  # Keep the largest move detected so far.
            if delta < delta_min:
                break  # Stable solution found, nothing is moving enough.

        return object_positions.tolist()  # Return updated position list.

    def separate_objects(
        self, positions, objects, k=0.1, dt=0.1, iterations=100, delta_min=4.0
    ):
        """
        Arrange Objects on an image without overlapping using physics calculations.
        !! This is NOT a full force-directed model. It just reduces overlaps.

        :param positions: List of [[x, y],...] initial positions of the Objects.
        :param objects: List of object sizes as [[width, height , fixed],...]
            : width: pixel width of object.
            : height: pixel height of object.
            : fixed: boolean to say this object cannot move.
        :param k: Repulsive constant
        :param dt: Time step for simulation
        :param iterations: Sets limit on time spent finding a solution.
        :param delta_min: When the largest movement in an iteration falls below this number of pixels, the loop terminates.
        :return: List of new object positions as [[x, y],...]

        """
        # The basis of this code was generated by Bing ChatGPT Sep.2023.
        width = self.get_width()
        height = self.get_height()

        # Initialize label positions at the object positions
        object_positions = np.array(positions, dtype=np.float)

        # Compute the distance matrix between all pairs of objects
        # pdist() generates a 'compressed' matrix of the distances between each object.
        # squareform() converts the compressed matrix into a 'redundant' matrix, but it's easier to find the distances between specific objects in this format.
        # distances = squareform(pdist(object_positions)) # Calculated in ChatGPT but not used.
        for m in range(iterations):  # Set limit to processing.

            # Note the positions at the start of the iteration.
            previous_positions = object_positions.copy()

            # Compute the force matrix between all pairs of objects
            forces = np.zeros_like(object_positions)

            # Calculate repulsive forces between objects.
            for i in range(len(objects)):
                for j in range(i + 1, len(objects)):
                    # Compute the overlap between objects i and j
                    object_i = objects[i]
                    object_j = objects[j]
                    object_i_fixed = object_i[2]
                    object_j_fixed = object_j[2]
                    overlap_x = max(
                        0,
                        (object_i[0] + object_j[0]) / 2
                        - abs(object_positions[i][0] - object_positions[j][0]),
                    )
                    overlap_y = max(
                        0,
                        (object_i[1] + object_j[1]) / 2
                        - abs(object_positions[i][1] - object_positions[j][1]),
                    )

                    # If there is an overlap, apply a repelling force
                    if overlap_x > 0 and overlap_y > 0:
                        direction = (
                            object_positions[i] - object_positions[j]
                        )  # Subtract [j] positions from [i] positions.
                        direction /= np.linalg.norm(
                            direction
                        )  # Convert to -1.0 <> 1.0 direction (array of (x,y) still).
                        force = (
                            direction * overlap_x * overlap_y * k
                        )  # Apply force to both axes (x,y).
                        if object_i_fixed == False:
                            forces[i] += force  # Apply force if object can move.
                        if object_j_fixed == False:
                            forces[j] -= force  # Apply force if object can move.

            # Apply a spring force to attract the label to the object
            for i in range(len(objects)):
                displacement = object_positions[i] - positions[i]
                dk = displacement * k
                forces[i] = forces[i] - dk

            # Update the label positions using the computed forces
            fd = forces * dt
            object_positions = object_positions + fd

            # Keep the objects within the image bounds
            for i in range(len(objects)):
                object_positions[i][0] = min(
                    max(object_positions[i][0], objects[i][0] / 2),
                    width - objects[i][0] / 2,
                )
                object_positions[i][1] = min(
                    max(object_positions[i][1], objects[i][1] / 2),
                    height - objects[i][1] / 2,
                )

            delta = 0  # What's the largest move detected after this iteration?
            for i, origpos in enumerate(
                previous_positions
            ):  # Check how far each object has moved in this iteration.
                newpos = object_positions[i]
                move = (
                    ((newpos[0] - origpos[0]) ** 2) + ((newpos[1] - origpos[1]) ** 2)
                ) ** 0.5
                delta = max(move, delta)  # Keep the largest move detected so far.
            # print ("SeparateObjects_full: m",m,"delta",delta)
            if delta < delta_min:
                break  # Stable solution found, nothing is moving enough.

        return (
            object_positions.tolist()
        )  # , max_overlap # Return updated position list & a measure of the maximum overlap.

    def rotate_buffer_about_point(self, imagebuffer, location, angle):
        """WIP: Building better angle text feature.
            location is (x,y) tuple

        Based upon code sample from https://theailearner.com/2020/11/02/how-to-write-rotated-text-using-opencv-python/
        """
        # *Q* Just a holder for a code snippet while under development.

        # Rotate the image using cv2.warpAffine()
        M = cv2.getRotationMatrix2D(location, angle, 1)
        imagebuffer = cv2.warpAffine(
            imagebuffer, M, (imagebuffer.shape[1], imagebuffer.shape[0])
        )
        return imagebuffer

    @staticmethod
    def overlay_buffer(imagebuffer, overlaybuffer, x, y):
        """WIP: Building better overlay/merge function.
        Based upon https://stackoverflow.com/questions/40895785/using-opencv-to-overlay-transparent-image-onto-another-image
        Take an overlaybuffer with transparency and apply it to the imagebuffer.
        imagebuffer is the original image that the overlay is applied to.
        overlaybuffer is the image to be placed on top of imagebuffer.
        overlaybuffer supports transparency channel (such as bgra format)
        x,y are the co-ordinates where the overlay will be placed on the original image.
        """

        imagebuffer_width = imagebuffer.shape[1]
        imagebuffer_height = imagebuffer.shape[0]
        if (
            x >= imagebuffer_width or y >= imagebuffer_height
        ):  # overlay is off the edge of the image.
            return imagebuffer
        h, w = overlaybuffer.shape[0], overlaybuffer.shape[1]  # Size of overlay.
        if x + w > imagebuffer_width:  # Clip overlay if it doesn't all fit.
            w = imagebuffer_width - x
            overlaybuffer = overlaybuffer[:, :w, :]
        if y + h > imagebuffer_height:  # Clip overlay if it doesn't all fit.
            h = imagebuffer_height - y
            overlaybuffer = overlaybuffer[:h, :, :]
        if (
            overlaybuffer.shape[2] < 4
        ):  # No transparency so just combine the two images directly.
            overlaybuffer = np.concatenate(
                [
                    overlaybuffer,
                    np.ones(
                        (overlaybuffer.shape[0], overlaybuffer.shape[1], 1),
                        dtype=overlaybuffer.dtype,
                    )
                    * 255,
                ],
                axis=2,
            )
        overlaybuffer_image = overlaybuffer[
            ..., :3
        ]  # Get the bgr channels of the overlay.
        mask = (
            overlaybuffer[..., 3:] / 255.0
        )  # Create a mask per pixel of the overlay based upon transparency of each pixel.
        # Apply the overlay.
        imagebuffer[y : y + h, x : x + w] = (1.0 - mask) * imagebuffer[
            y : y + h, x : x + w
        ] + mask * overlaybuffer_image
        return imagebuffer

    def rotate_image(self, angle):
        """Accepts 0,90,180,270"""
        self.log("pilomarimage", self.name, ".RotateImage(", angle, ")", terminal=False)
        angle = angle % 360  # Always in range 0-360 degrees.
        if angle >= 45 and angle < 135:
            rotateCode = cv2.ROTATE_90_CLOCKWISE
        elif angle >= 135 and angle < 225:
            rotateCode = cv2.ROTATE_180
        elif angle >= 225 and angle < 315:
            rotateCode = cv2.ROTATE_90_COUNTERCLOCKWISE
        else:
            rotateCode = None
        if rotateCode is not None:
            self.image_buffer = cv2.rotate(self.image_buffer, rotateCode)
            self.modified_timestamp = self.now_utc()
            self.action_list.append(["rotateimage", angle])
        return True

    def count_stars(self, minval=3, maxval=650, maxstars=500, threshold=100):
        """Count the number of stars in an image.
        From: https://stackoverflow.com/questions/48154642/how-to-count-number-of-dots-in-an-image-using-python-and-opencv

        Doesn't modify image_buffer.

        minval = Minimum area of stars.
        maxval = Maximum area of stars.
        maxstars = Maximum number of stars to return .
        threshold = The brightness level (0-255) above which something is considered a star.
        """

        self.log(
            "pilomarimage",
            self.name,
            ".CountStars(",
            minval,
            ",",
            maxval,
            ")",
            terminal=False,
        )
        cvimagebuffer = self.new_buffer_type(
            "grayscale"
        )  # Return a copy of the image buffer in grayscale.
        # Threshold the image to make it more crisp.
        temp, threshed = cv2.threshold(
            cvimagebuffer, threshold, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
        )
        # findcontours to identify 'dots' (contours) in the image. This will recognise STARS and also some patterns made by stars. So it needs filtering.
        dots = cv2.findContours(threshed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[-2]
        # filter the 'dots' by their area. Small ones are stars, large ones are some other artifact.
        starcount = 0
        starlist = []
        for dot in dots:  # Check each dot in turn.
            if (
                minval < cv2.contourArea(dot) < maxval
            ):  # We only want small dots to count as stars.
                starcount += 1  # Increment count.
                dot_x, dot_y, dot_w, dot_h = cv2.boundingRect(
                    dot
                )  # Bordering rectangle of dot.
                dot_radius = int(
                    (dot_w + dot_h) / 4
                )  # Half average of width and height.
                ctr_x = int(dot_x + dot_w / 2)  # x center of dot.
                ctr_y = int(dot_y + dot_h / 2)  # y center of dot.
                staritem = [ctr_x, ctr_y, dot_radius]
                starlist.append(staritem)  # Construct list of star locations.
            if starcount >= maxstars:
                self.log(
                    "pilomarimage",
                    self.name,
                    ".CountStars:",
                    maxstars,
                    "star limit hit.",
                    terminal=False,
                )
                break
        self.star_list = starlist
        self.star_count = starcount
        self.calculate_star_spread()  # How widely spread are the stars across the image? Indicates good/bad tracking tuning.
        self.log(
            "pilomarimage",
            self.name,
            ".CountStars: End. Counted",
            starcount,
            terminal=False,
        )
        return starcount, starlist

    def b_vrange(self, BV):
        # Given a B-V value, pick the pair of pilomarimage.COLORPOINTS that will be used to calculate the RGB equivalent.
        fromi = 0
        toi = 1  # If BV is too low, we use the lowest pair of entries. (We will extrapolate a value)
        try:
            for i, cp in enumerate(
                PilomarImage.COLORPOINTS
            ):  # Consider each sample point in turn.
                if BV >= cp[0]:  # Above lower threshold of this sample point.
                    fromi = i  # Interpolation starts with this lower entry.
                    toi = i + 1  # Interpolation ends with the next entry.
            if toi >= len(
                PilomarImage.COLORPOINTS
            ):  # If BV is too high, we are off the end of the list, so use the highest pair of entries.
                toi = len(PilomarImage.COLORPOINTS) - 1
                fromi = toi - 1
        except Exception as e:
            self.log(
                "pilomarimage",
                self.name,
                ".BVRange:",
                str(BV),
                "failed:",
                str(e),
                level="error",
            )
            fromi = 0
            toi = 1
        return fromi, toi

    def b_vd_x(self, fromi, toi):
        # Span of BV values from LOWER to UPPER sample limits.
        try:
            result = (
                PilomarImage.COLORPOINTS[toi][0] - PilomarImage.COLORPOINTS[fromi][0]
            )
        except Exception as e:
            self.log(
                "pilomarimage",
                self.name,
                ".BVdX:",
                str(fromi),
                str(toi),
                "failed:",
                str(e),
                level="error",
            )
            result = 0
        return result

    def b_vd_r(self, fromi, toi):
        # Span of BLUE channel values from LOWER to UPPER sample limits.
        try:
            result = (
                PilomarImage.COLORPOINTS[toi][1][0]
                - PilomarImage.COLORPOINTS[fromi][1][0]
            )
        except Exception as e:
            self.log(
                "pilomarimage",
                self.name,
                ".BVdR:",
                str(fromi),
                str(toi),
                "failed:",
                str(e),
                level="error",
            )
            result = 0
        return result

    def b_vd_g(self, fromi, toi):
        # Span of GREEN channel values from LOWER to UPPER sample limits.
        try:
            result = (
                PilomarImage.COLORPOINTS[toi][1][1]
                - PilomarImage.COLORPOINTS[fromi][1][1]
            )
        except Exception as e:
            self.log(
                "pilomarimage",
                self.name,
                ".BVdG:",
                str(fromi),
                str(toi),
                "failed:",
                str(e),
                level="error",
            )
            result = 0
        return result

    def b_vd_b(self, fromi, toi):
        # Span of BLUE channel values from LOWER to UPPER sample limits.
        try:
            result = (
                PilomarImage.COLORPOINTS[toi][1][2]
                - PilomarImage.COLORPOINTS[fromi][1][2]
            )
        except Exception as e:
            self.log(
                "pilomarimage.",
                self.name,
                "BVdB:",
                str(fromi),
                str(toi),
                "failed:",
                str(e),
                level="error",
            )
            result = 0
        return result

    def bv_interpolate(self, BV, fromi, toi):
        try:
            BVProportion = (BV - PilomarImage.COLORPOINTS[fromi][0]) / BVdX(
                fromi, toi
            )  # Position of our point between the two reference points. This is the scale applied to R,G,B channels.
            r = round(
                (BVProportion * BVdR(fromi, toi))
                + PilomarImage.COLORPOINTS[fromi][1][0],
                0,
            )  # Scale RED channel relative to the BV position.
            r = max(0, r)  # Colour channel values must be 0-255
            r = min(255, r)
            g = round(
                (BVProportion * BVdG(fromi, toi))
                + PilomarImage.COLORPOINTS[fromi][1][1],
                0,
            )  # Scale GREEN channel relative to the BV position.
            g = max(0, g)
            g = min(255, g)
            b = round(
                (BVProportion * BVdB(fromi, toi))
                + PilomarImage.COLORPOINTS[fromi][1][2],
                0,
            )  # Scale BLUE channel relative to the BV position.
            b = max(0, b)
            b = min(255, b)
        except Exception as e:
            self.log(
                "pilomarimage.",
                self.name,
                "BVInterpolate:",
                str(BV),
                str(fromi),
                str(toi),
                "failed:",
                str(e),
                level="error",
            )
            r = b = g = 255
        return (int(b), int(g), int(r))

    def b_vto_bgr(self, BV):  # 1 references.
        """Convert a B-V color value from Hipparcos catalog to an approximate BGR color code.
        B-V     R G B (hex)
        -0.33   706ffe
        -0.3    519ffe
        -0.02   bfd0ff
        0.3     cdfdff
        0.58    eeffdf
        0.81    ffff7f
        1.40    fe7f7d
        """
        r = g = b = 255
        try:
            fromi, toi = self.b_vrange(
                BV
            )  # Which pair of sample colour points do we interpolate from?
            b, g, r = self.bv_interpolate(BV, fromi, toi)
        except Exception as e:
            self.log(
                "pilomarimage.",
                self.name,
                "BVtoBGR:",
                str(BV),
                "failed:",
                str(e),
                level="warning",
            )
            b = g = r = 255
        return (b, g, r)

    def mark_location(self, starx, stary, color, uppertext=None, lowertext=None):
        """Write the location text next to the star.
        Places the text left/right depending upon it's location in the image.
        Write any 'text' value above center of star."""
        starx = int(starx)
        stary = int(stary)
        if starx < (self.get_width() / 2):
            xloc = starx + 10
        else:
            xloc = starx - 120
        yloc = stary
        loctext = "(" + str(starx) + "," + str(stary) + ")"
        self.add_text(loctext, xloc, yloc, color, 0.5)
        if uppertext is not None:  # There's additional info to print above the star.
            self.add_text(uppertext, starx - 10, yloc - 20, color, 0.5)
        if lowertext is not None:  # There's additional info to print above the star.
            self.add_text(lowertext, starx - 10, yloc + 30, color, 0.5)
        return True

    def scale_star_list(self, scalefactor):
        """Take a list of star locations and scale the first two terms.
        Any additional terms are left unmodified.
        Each star in the list consists of x,y image positions.
            [xpos,ypos]
        Only the xpos and ypos entries are scaled, any extra terms remain unchanged."""
        self.log(
            "pilomarimage",
            self.name,
            ".ScaleStarList: Scale:",
            scalefactor,
            terminal=False,
        )
        newlist = []  # The resulting list.
        for star in self.star_list:  # Go through each star in turn.
            newstar = []
            for i, term in enumerate(star):
                if i < 2:
                    newterm = term * scalefactor
                else:
                    newterm = term
                newstar.append(int(newterm))
            newlist.append(newstar)
        self.star_list = newlist
        self.action_list = [["scalestarlist", scalefactor]]
        self.log(
            "pilomarimage",
            self.name,
            ".ScaleStarList: Result:",
            newlist,
            terminal=False,
        )
        return True

    def image_exists(self):
        """Return True if the image_buffer is initialised."""
        if isinstance(self.image_buffer, type(None)):
            return False
        else:
            return True

    def image_missing(self):
        """Return TRUE if image_buffer is not initialized."""
        result = False
        if isinstance(self.image_buffer, type(None)):
            result = True
        return result

    def simplify_image(self, blurradius=13):
        """Backwards compatibility with earlier versions."""
        print(
            "pilomarimage.SimplifyImage(): Deprecated. Please use pilomarimage.EnhanceStars() method now."
        )
        self.log(
            "pilomarimage",
            self.name,
            ".SimplifyImage -> EnhanceStars: Begin",
            terminal=False,
        )
        return self.enhance_stars(blurradius=blurradius)

    def prepare_image(self, blurradius=13):
        """Backwards compatibility with earlier versions."""
        print(
            "pilomarimage.PrepareImage(): Deprecated. Please use pilomarimage.EnhanceStars() method now."
        )
        self.log(
            "pilomarimage",
            self.name,
            ".PrepareImage -> EnhanceStars: Begin",
            terminal=False,
        )
        return self.enhance_stars(blurradius=blurradius)

    def enhance_stars(self, blurradius=13, cloudthresh=100, starthresh=16, maxval=255):
        """Enhance the stars in the image.
        Was 'SimplifyImage' and 'PrepareImage' in earlier pilomar versions.
        - blurradius is the GaussianBlur radius.
        - cloudthresh is the threshold to remove cloud (experimental).
        - starthresh is the threshold to single out the stars.
        - maxval is the saturated value set for cells above the threshold."""
        self.log(
            "pilomarimage",
            self.name,
            ".EnhanceStars: blurradius",
            blurradius,
            "cloudthresh",
            cloudthresh,
            "starthresh",
            starthresh,
            "maxval",
            maxval,
            terminal=False,
        )
        if self.image_missing():
            print("pilomarimage", self.name, ".EnhanceStars: No image in the buffer.")
        self.change_type("grayscale")  # Convert to grayscale.
        retval, self.image_buffer = cv2.threshold(
            self.image_buffer, cloudthresh, maxval, cv2.THRESH_BINARY
        )  # 100 should ignore clouds more easily and just recognise brighter stars.
        if blurradius % 2 == 0:
            blurradius += 1  # Must be odd.
        # 2nd enlarge the stars using a blur filter.
        # - This increases the radius of each star, so when we reduce the image size, the star survives the shrinking.
        self.image_buffer = cv2.GaussianBlur(
            self.image_buffer, (blurradius, blurradius), 0
        )
        # 3rd sharpen these larger star dots back into more definite black-or-white.
        # - Use adaptive thresholding now to make the stars more crisp.
        # - Adaptive means that the threshold limit between BLACK and WHITE is chosen by the function.
        retval, self.image_buffer = cv2.threshold(
            self.image_buffer, starthresh, maxval, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )  # OTSU is adaptive threshold limits.
        self.action_list.append(["enhancestars", blurradius])
        self.modified_timestamp = self.now_utc()
        self.log("pilomarimage", self.name, ".EnhanceStars: End.", terminal=False)
        return True

    def fs_save(self, filterdata):
        """Save the current image buffer and write the current filter data on it.
        A debugging feature.

        filterdata is the data you want writing as a dictionary.
        'saveas' entry must exist in the filterdata.
        """
        if "saveas" in filterdata:  # There is a filename to use.
            filename = filterdata["saveas"]
            if filename is not None and len(filename) > 0:
                # Add filterdata information to the image.
                self.add_text(
                    "filterdata:",
                    x=10,
                    y=int(self.get_height() / 2),
                    color=PilomarImage.BGRColor["White"],
                    bgcolor=PilomarImage.BGRColor["Black"],
                )
                for key, value in filterdata.items():
                    self.add_text(
                        " " + str(key) + ":" + str(value),
                        x=10,
                        y=self.next_text_y,
                        color=PilomarImage.BGRColor["White"],
                        bgcolor=PilomarImage.BGRColor["Black"],
                    )
                self.save(filename)
        return True

    def fs_grayscale(self, filterdata):
        """Convert buffer to grayscale.
        {'method':'grayscale',
         'comment':''}"""
        comment = filterdata.get(
            "comment", ""
        )  # Get any associated comment, default ''.
        if comment != "":
            self.log(
                "pilomarimage",
                self.name,
                ".FS_Grayscale: Comment:",
                comment,
                terminal=False,
            )
        self.log("pilomarimage", self.name, ".FS_Grayscale:", terminal=False)
        self.change_type("grayscale")  # Convert to grayscale.
        self.action_list.append(["FS_Grayscale"])
        self.modified_timestamp = self.now_utc()
        return True

    def fs_threshold(self, filterdata):
        """Run OpenCV threshold filter on current image buffer using input parameters.
        filterdata = dictionary of parameters.

        {'method':'threshold',
         'threshold': 127,
         'maxval': 255,
         'type': cv2.THRESH_BINARY,
         'comment': ''}

        """
        threshold = filterdata.get(
            "threshold", 127
        )  # Get threshold level, default 127.
        maxval = filterdata.get(
            "maxval", 255
        )  # Get output value for pixels above the threshold, default 255.
        threshold_type = filterdata.get(
            "type", cv2.THRESH_BINARY
        )  # Get threshold calculation type, default THRESH_BINARY.
        if threshold_type is None:
            threshold_type = cv2.THRESH_BINARY
        comment = filterdata.get(
            "comment", ""
        )  # Get any associated comment, default ''.
        if comment != "":
            self.log(
                "pilomarimage",
                self.name,
                ".FS_Threshold: Comment:",
                comment,
                terminal=False,
            )
        self.log(
            "pilomarimage",
            self.name,
            ".FS_Threshold(",
            threshold,
            ",",
            maxval,
            ",",
            threshold_type,
            ")",
            terminal=False,
        )
        calculatedthreshold, self.image_buffer = cv2.threshold(
            self.image_buffer, threshold, maxval, threshold_type
        )
        self.action_list.append(["FS_Threshold", threshold, maxval, threshold_type])
        self.modified_timestamp = self.now_utc()
        return True

    def fs_gaussian_blur(self, filterdata):
        """Run OpenCV gaussianblur filter on current image buffer using input parameters.
        filterdata = dictionary of parameters.

        {'method':'gaussianblur',
         'radius': 5, # Must be 0 or an odd integer.
         'comment': ''}

        """
        radius = filterdata.get("radius", 5)  # Get blur radius, default 5.
        if radius < 0:
            radius = 0  # Cannot be negative.
        if radius > 0 and radius % 2 == 0:
            radius += 1  # Must be odd if > 0.
        comment = filterdata.get(
            "comment", ""
        )  # Get any associated comment, default ''.
        if comment != "":
            self.log(
                "pilomarimage",
                self.name,
                ".FS_GaussianBlur: Comment:",
                comment,
                terminal=False,
            )
        self.log(
            "pilomarimage", self.name, ".FS_GaussianBlur(", radius, ")", terminal=False
        )
        self.image_buffer = cv2.GaussianBlur(self.image_buffer, (radius, radius), 0)
        self.action_list.append(["FS_GaussianBlur", radius])
        self.modified_timestamp = self.now_utc()
        return True

    def fs_dehaze(self, filterdata):
        """Remove general haze gradient from an image buffer.
        filterdata = dictionary of parameters.

        {'method':'dehaze',
         'samples':1, # Compress horizontal pixel values down to this number of samples per line.
         'strength':100 # 0 - 100 (%) strength. How much of the identified haze will be removed.
         'comment': ''}
        """
        samples = filterdata.get(
            "samples", 1
        )  # Number of samples along each image row, default 1
        strength = filterdata.get(
            "strength", 100
        )  # How strong is the filter, default 100 (%).
        comment = filterdata.get(
            "comment", ""
        )  # Get any associated comment, default ''.
        if comment != "":
            self.log(
                "pilomarimage",
                self.name,
                ".FS_Dehaze: Comment:",
                comment,
                terminal=False,
            )
        self.log(
            "pilomarimage",
            self.name,
            ".FS_Dehaze(",
            samples,
            ",",
            strength,
            ")",
            terminal=False,
        )
        # Create a working buffer to construct the haze filter.
        buffer = (
            self.image_buffer.copy()
        )  # Copy the image buffer, we will blur this copy.
        buffer = self.horizontal_blur_buffer(
            buffer, band=samples
        )  # Horizontally blur the buffer.
        if strength > 0:  # There needs to be some effect.
            if strength != 100:  # Multiply all the channels appropriately.
                buffer = self.percentage_buffer(
                    buffer, strength
                )  # Reduce the strength of the buffer.
            self.subtract_buffer(
                buffer
            )  # Subtract the blurred buffer from the master image buffer.
        self.action_list.append(["FS_Dehaze", samples, strength])
        self.modified_timestamp = self.now_utc()
        return True

    def run_filter_script(self, scriptname):
        """Given a script name, apply the filters and parameters defined in the script.
        filterrules is a dictionary"""
        self.log("pilomarimage", self.name, ".RunFilterScript()", terminal=False)
        if not type(scriptname) == str:  # Nothing useful set.
            self.log("RunFilterScript(): No valid script name.", terminal=False)
            print("RunFilterScript(): No valid script name.")
            return False
        if not scriptname in PilomarImage.FILTERSCRIPTS:  # Script doesn't exist.
            self.log(
                "RunFilterScript(",
                scriptname,
                "). Script does not exist.",
                terminal=False,
            )
            print("RunFilterScript(", scriptname, "). Script does not exist.")
            return False
        filterscript = PilomarImage.FILTERSCRIPTS[scriptname]

        filtercount = 0
        result = True

        for (
            entryname,
            filterdata,
        ) in filterscript.items():  # Go through each set of filters in turn.
            self.log(
                "pilomarimage.RunFilterScript(",
                filtercount,
                entryname,
                ") Running script...",
                terminal=False,
            )  # Report the name of the filter
            # Each 'item' should be a sub-dictionary of a filter and its parameters to apply to the current image.
            filtermethod = filterdata["method"]
            result = True
            if filtermethod == "dehaze":
                result = self.fs_dehaze(filterdata)  # Remove haze from the image.
            elif filtermethod == "gaussianblur":
                result = self.fs_gaussian_blur(
                    filterdata
                )  # Apply a Gaussian blur filter.
            elif filtermethod == "grayscale":
                result = self.fs_grayscale(filterdata)  # Convert image to grayscale.
            elif filtermethod == "save":
                result = self.fs_save(filterdata)  # Apply a threshold filter.
            elif filtermethod == "threshold":
                result = self.fs_threshold(filterdata)  # Apply a threshold filter.
            else:  # Filter method is not recognised.
                self.log(
                    "pilomarimage.RunFilterScript(",
                    filtercount,
                    entryname,
                    ") filtermethod",
                    filtermethod,
                    "does not exist.",
                    level="error",
                )
                print(
                    "**ERROR** pilomarimage.RunFilterScript(",
                    filtercount,
                    entryname,
                    ") filtermethod",
                    filtermethod,
                    "does not exist.",
                )
                result = False
            if not result:
                break  # Failure.
            filtercount += 1  # Increment count.
        if not result:
            self.log(
                "pilomarimage.RunFilterScript(",
                scriptname,
                ") did not complete successfully.",
                level="warning",
            )
            print(
                "WARNING: pilomarimage.RunFilterScript(",
                scriptname,
                ") did not complete successfully.",
            )
        return result

    def urban_filter(
        self,
        band=1,
        blurradius=2,
        cloudthresh=50,
        starthresh=16,
        maxval=255,
        strength=100,
    ):
        """Primitive 'urban skies' filter.
        This is used for star drift tracking.
        A live image is cleaned to remove common urban haze before enhancing the remaining stars.
        band = Blurring factor. '1' is the highest blurring.
        blurradius, cloudthresh, starthresh, maxval are all values for the EnhanceStars() method.
        strength is the percentage strength of the haze filter.
        0 = No haze reduction.
        50 = 50% haze reduction.
        100 = Full haze reduction."""
        self.log(
            "pilomarimage",
            self.name,
            ".UrbanFilter(): band",
            band,
            "blurradius",
            blurradius,
            "cloudthresh",
            cloudthresh,
            "starthresh",
            starthresh,
            "maxval",
            maxval,
            "strength",
            strength,
            terminal=False,
        )
        buffer = (
            self.image_buffer.copy()
        )  # Copy the image buffer, we will blur this copy.
        buffer = self.horizontal_blur_buffer(
            buffer, band=band
        )  # Horizontally blur the buffer.
        if strength > 0:  # There needs to be some effect.
            if strength != 100:  # Multiply all the channels appropriately.
                buffer = self.percentage_buffer(
                    buffer, strength
                )  # Reduce the strength of the buffer.
            self.subtract_buffer(
                buffer
            )  # Subtract the blurred buffer from the master image buffer.
        self.enhance_stars(
            blurradius=blurradius,
            cloudthresh=cloudthresh,
            starthresh=starthresh,
            maxval=maxval,
        )  # Enhance the stars that remain.
        return True

    def hsv2bgr(self, hue, sat, val):
        """Convert 3 separate Hue,Saturation,Value values into Blue,Green,Red."""
        hsv = np.uint8([[[hue, sat, val]]])  # a 1x1 pixel image.
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        b = int(bgr[0][0][0])
        g = int(bgr[0][0][1])
        r = int(bgr[0][0][2])
        return b, g, r

    def dim_channel(self, channel, ratio):  # 3 references.
        """simple multiplier for single color channel.
        ratio = 0.0 - 1.0"""
        channel = channel * ratio
        channel = min(max(channel, 0), 255)  # 0 <= x <= 255
        return channel

    def dim_color(self, color, ratio):  # 4 references.
        """Simple multiplier for BGR or BGRA color tuples.
        ratio = 0.0 - 1.0"""
        if len(color) == 4:  # Adjust BGR, but not A.
            return (
                self.dim_channel(color[0], ratio),
                self.dim_channel(color[1], ratio),
                self.dim_channel(color[2], ratio),
                color[3],
            )
        elif len(color) == 3:  # Adjust BGR
            return (
                self.dim_channel(color[0], ratio),
                self.dim_channel(color[1], ratio),
                self.dim_channel(color[2], ratio),
            )
        else:
            return dim_channel(color, ratio)  # Assume single channel.

    def fake_field(self):  # Generate fake field noise.
        """Create a small blank image and add some fake electronic noise to it.
        Then enlarge the image to match the size of the target image.
        Then combine the two images.
        *Q* Only handles bgr images at the moment."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FakeField: No image in the buffer.")
        height = self.get_height()
        width = self.get_width()
        fieldimg = np.zeros(
            (int(height / 100), int(width / 100), 3), np.uint16
        )  # 'bgr' at 1% of original size.
        fieldimg = cv2.circle(
            fieldimg,
            (fieldimg.shape[1], fieldimg.shape[0]),
            int(fieldimg.shape[1] / 3),
            PilomarImage.BGRColor["VeryDarkRed"],
            thickness=-1,
        )  # Simulate an electric field shadow.
        fieldimg = cv2.resize(
            fieldimg, (width, height), interpolation=self.resize_method
        )  # Scale back up to full image size.
        fieldimg = np.add(self.image_buffer, fieldimg)  # Combine
        self.image_buffer = np.clip(fieldimg, 0, 255).astype(
            np.uint8
        )  # Clip to uint8 values.
        self.action_list.append(["fakefield"])
        self.modified_timestamp = self.now_utc()
        return True

    def fake_noise(self):  # Generate fake image noise.
        """Create a small blank image and add some fake image noise to it.
        Return the combined image.
        *Q* Only handles bgr images at the moment."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FakeNoise: No image in the buffer.")
        fieldimg = np.random.randint(
            0, 25, (self.get_height(), self.get_width(), 3), np.uint16
        )  # 'bgr' buffer of random values.
        fieldimg = np.add(fieldimg, self.image_buffer)
        self.image_buffer = np.clip(fieldimg, 0, 255).astype(
            np.uint8
        )  # Clip to uint8 values.
        self.action_list.append(["fakenoise"])
        self.modified_timestamp = self.now_utc()
        return True

    def trim_line(self, x1, y1, x2, y2, trimfactor=None, trimpixels=None):
        """Trim an amount off each end of a line.
        Given start and end locations and the amount to trim.
        trimfactor = 0.0 - 0.5 The proportion of the line to remove from each end.
        trimpixels = nnn The number of pixels to trim from each end."""
        if trimpixels is not None:  # Convert pixel count to factor.
            length = int(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
            if length != 0.0:
                trimfactor = trimpixels / length
            else:
                trimfactor = 0.0
        if trimfactor is None:  # No value.
            return False
        xstart = int(
            self.interpolate(y1, x1, y2, x2, y1 + ((y2 - y1) * trimfactor))
        )  # start xx% into the path.
        ystart = int(
            self.interpolate(x1, y1, x2, y2, x1 + ((x2 - x1) * trimfactor))
        )  # start xx% into the path.
        xend = int(
            self.interpolate(y1, x1, y2, x2, y1 + ((y2 - y1) * (1 - trimfactor)))
        )  # end xx% from end of the path.
        yend = int(
            self.interpolate(x1, y1, x2, y2, x1 + ((x2 - x1) * (1 - trimfactor)))
        )  # end xx% from end of the path.
        return xstart, ystart, xend, yend

    def fake_meteor(self):  # Generate fake meteor streak
        """Add a random meteor like streak to an image.
        *Q* Only handles bgr images at the moment."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FakeMeteor: No image in the buffer.")
        color = self.safe_color(PilomarImage.BGRColor["White"])
        width = self.get_width()
        height = self.get_height()
        meteorimg = np.zeros((height, width, 3), np.uint16)  # 'bgr' buffer of zeros.
        length = 0
        while length < 500:  # Make the meteor streak long enough to see.
            x1 = random.randint(0, width)
            x2 = random.randint(0, width)
            y1 = random.randint(0, height)
            y2 = random.randint(0, height)
            length = int(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
        meteorimg = cv2.line(
            meteorimg, (x1, y1), (x2, y2), color, 1
        )  # Mark the thin main trail on the image.
        # Flare the meteor mid path...
        xstart, ystart, xend, yend = self.trim_line(
            x1, y1, x2, y2, 0.3
        )  # Find the central part of the line to create a flare in the trail.
        # xstart = int(self.interpolate(y1,x1,y2,x2,y1 + ( (y2 - y1) * 0.3) ) ) # start 30% into the path.
        # ystart = int(self.interpolate(x1,y1,x2,y2,x1 + ( (x2 - x1) * 0.3) ) ) # start 30% into the path.
        # xend = int(self.interpolate(y1,x1,y2,x2,y1 + ( (y2 - y1) * 0.7) ) ) # end 30% from end of the path.
        # yend = int(self.interpolate(x1,y1,x2,y2,x1 + ( (x2 - x1) * 0.7) ) ) # end 30% from end of the path.
        meteorimg = cv2.line(
            meteorimg, (xstart, ystart), (xend, yend), color, 3
        )  # Mark a thicker flare trail on the image.
        meteorimg = np.add(meteorimg, self.image_buffer)
        self.image_buffer = np.clip(meteorimg, 0, 255).astype(
            np.uint8
        )  # Clip to uint8 values.
        self.action_list.append(["fakemeteor"])
        self.modified_timestamp = self.now_utc()
        return True

    def plot_stars(self, radius, starlist):
        """Given an existing image buffer and a list of stars, create a clean version of the image.
        Inherit the dimensions from the source image, and place the stars according to the starlist.
        This returns a GRAYSCALE image with all stars depicted at the same size.
        The size is the same for LATEST and TARGET images (Parameters.TrackingStarRadius), so that the
        FindTransform() method has consistent images to compare."""
        self.log("pilomarimage", self.name, ".PlotStars(", radius, ")", terminal=False)
        if self.image_missing():
            print("pilomarimage", self.name, ".PlotStars: No image in the buffer.")
        GrayscaleWhite = 255
        self.new(
            self.get_dimensions(), "grayscale", np.uint8
        )  # GRAYSCALE image. HEIGHT, WIDTH inherited from reference image.
        for star_x, star_y, star_r in starlist:
            self.image_buffer = cv2.circle(
                self.image_buffer,
                (star_x, star_y),
                radius,
                GrayscaleWhite,
                thickness=-1,
            )  # White. All stars converted to standard 7 pixel radius.
        self.action_list.append(["plotstars", radius])
        self.modified_timestamp = self.now_utc()
        return True

    def measure_contrast(self):
        """Return values representing contrast of overall image.
        2 contrast calculations are returned.
        1) Michelson contrast (0.0 - 1.0)
        2) standard deviation contrast
        Doesn't modify image_buffer
        """
        if self.image_missing():
            print(
                "pilomarimage", self.name, ".MeasureContrast: No image in the buffer."
            )
        michelson_contrast = None
        stddev_contrast = None
        cvimagebuffer = self.new_buffer_type("grayscale")  # Needs grayscale buffer.
        try:
            stddev_contrast = cvimagebuffer.std()  # Standard deviation.
        except Exception as e:
            self.log(
                "pilomarimage",
                self.name,
                ".MeasureContrast: stddev_contrast failed.",
                terminal=False,
            )
        try:
            min = float(np.min(cvimagebuffer))
            max = float(np.max(cvimagebuffer))
            michelson_contrast = (max - min) / (max + min)  #
        except Exception as e:
            self.log(
                "pilomarimage",
                self.name,
                ".MeasureContrast: michelson_contrast failed.",
                terminal=False,
            )
        self.log(
            "pilomarimage",
            self.name,
            ".MeasureContrast: min",
            min,
            ", max",
            max,
            ", michelson_contrast",
            michelson_contrast,
            "stddev_contrast",
            stddev_contrast,
            terminal=False,
        )
        return michelson_contrast, stddev_contrast

    def fill_color(self, color):
        """Fill the image buffer with a specific color."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FillColor: No image in the buffer.")
        color = self.safe_color(color)
        if (
            self.get_type == "grayscale"
        ):  # Single depth grayscale image. Just fill all cells with the same value.
            self.image_buffer[:, :] = color[0]
        else:  # Multiple channels.
            for i, c in enumerate(color):  # Handle each channel separately.
                if self.image_buffer.shape[2] > i:  # Channel must exist.
                    self.image_buffer[:, :, i] = c  # Set all values of the channel.
        self.action_list.append(["fillcolor", color])
        self.modified_timestamp = self.now_utc()
        return True

    def in_bounds(self, x, y):
        """Return TRUE if (x,y) is within the bounds of the image."""
        width = self.get_width()
        height = self.get_height()
        if x >= 0 and x <= width and y >= 0 and y <= height:
            result = True
        else:
            result = False
        return result

    def out_of_bounds(self, x, y):
        """Return TRUE if (x,y) is outside the bounds of the image."""
        result = not self.in_bounds(x, y)
        return result

    def safe_thickness(self, thickness):
        """Default line thickness if not specified."""
        if thickness is None:
            thickness = 1
        return thickness

    def get_pen_color(self):
        """Return current pen color."""
        return self.pen_color

    def set_pen_color(self, color):
        """Set current pen color."""
        self.pen_color = self.safe_color(
            color
        )  # Make sure color depth matches image depth.
        self.action_list.append(["setpencolor", color])
        return True

    def set_pen_opacity(self, opacity):
        """Change the opacity of the current color."""
        if self.get_depth() == 4:  # Opacity supported.
            color = self.get_pen_color()
            color = (color[0], color[1], color[2], opacity)
            self.set_pen_color(color)
        self.action_list.append(["setpenopacity", opacity])
        return True

    def safe_color(self, color, default=None):
        """Default color if not specified."""
        depth = self.get_depth()
        if type(color) == type(None):
            color = default
        if type(color) == type(None):
            color = self.get_pen_color()
        if type(color) == type(None):
            if depth == 1:
                color = 255  # Grayscale
            elif depth == 3:
                color = PilomarImage.BGRColor["Black"]  # BGR
            elif depth == 4:
                color = (255, 255, 255, 255)  # BGRA
        # Convert color (received as int or tuple) into a list for looping through.
        if isinstance(color, int):
            ct = [color]
        else:
            ct = list(color)
        ctl = len(ct)
        if ctl != depth:  # We need to adjust the color tuple to match the image depth.
            if ctl == 1:
                if depth == 3:
                    color = (ct[0], ct[0], ct[0])  # From 1 to 3
                elif depth == 4:
                    color = (ct[0], ct[0], ct[0], 255)  # From 1 to 4
            elif ctl == 3:
                if depth == 1:
                    color = int((ct[0] + ct[1] + ct[2]) / 3)  # From 3 to 1
                elif depth == 4:
                    color = (ct[0], ct[1], ct[2], 255)  # From 3 to 4
            elif ctl == 4:
                if depth == 1:
                    color = int((ct[0] + ct[1] + ct[2]) / 3)  # From 4 to 1
                elif depth == 3:
                    color = tuple(color[:3])  # From 4 to 3
        return color

    def delta_color(self, color, delta):
        """Apply delta values to a color.
        Use this to nudge colors up/down slightly."""
        color = self.safe_color(color)
        color = list(color)  # Convert to list.
        delta = list(delta)  # Convert to list.
        for i in range(len(delta)):
            channel = color[i] + delta[i]  # Apply delta.
            channel = min(255, max(0, channel))  # Clip to 0-255 range.
            newcol[i] = channel  # Reapply
        if len(color) < 2:
            newcolor = newcol[0]  # single channel colors return just an integer.
        else:  # Multiple channel colors return a tuple.
            newcolor = tuple(newcol)
        return newcolor

    def draw_line(
        self, startcoord, endcoord, color=None, thickness=None, arrowpixels=None
    ):
        """Use opencv linedrawing."""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawLine: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        startcoord = self.orient_coord(startcoord)  # Make sure HEIGHT is right way up.
        endcoord = self.orient_coord(endcoord)  # Make sure HEIGHT is right way up.
        distance = math.sqrt(
            ((endcoord[0] - startcoord[0]) ** 2) + ((endcoord[1] - startcoord[1]) ** 2)
        )
        if arrowpixels is None or distance <= 0:
            self.image_buffer = cv2.line(
                self.image_buffer,
                startcoord,
                endcoord,
                color,
                thickness=thickness,
                lineType=cv2.LINE_AA,
            )
        else:
            arrowproportion = (
                arrowpixels / distance
            )  # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
            self.image_buffer = cv2.arrowedLine(
                self.image_buffer,
                startcoord,
                endcoord,
                color,
                thickness=thickness,
                line_type=cv2.LINE_AA,
                tipLength=arrowproportion,
            )
        self.action_list.append(
            ["drawline", startcoord, endcoord, color, thickness, arrowpixels]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_edge_line(
        self,
        startcoord,
        endcoord,
        color=None,
        edgecolor=None,
        thickness=None,
        edgethickness=1,
        arrowpixels=None,
    ):
        """Use opencv linedrawing."""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawEdgeLine: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        edgecolor = self.safe_color(edgecolor)
        startcoord = self.orient_coord(startcoord)  # Make sure HEIGHT is right way up.
        endcoord = self.orient_coord(endcoord)  # Make sure HEIGHT is right way up.
        if arrowpixels is None:
            self.image_buffer = cv2.line(
                self.image_buffer,
                startcoord,
                endcoord,
                edgecolor,
                thickness=int(thickness + (2 * edgethickness)),
                lineType=cv2.LINE_AA,
            )
            self.image_buffer = cv2.line(
                self.image_buffer,
                startcoord,
                endcoord,
                color,
                thickness=thickness,
                lineType=cv2.LINE_AA,
            )
        else:
            distance = math.sqrt(
                ((endcoord[0] - startcoord[0]) ** 2)
                + ((endcoord[1] - startcoord[1]) ** 2)
            )
            arrowproportion = (
                arrowpixels / distance
            )  # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
            self.image_buffer = cv2.arrowedLine(
                self.image_buffer,
                startcoord,
                endcoord,
                edgecolor,
                thickness=int(thickness + (2 * edgethickness)),
                line_type=cv2.LINE_AA,
                tipLength=arrowproportion,
            )
            self.image_buffer = cv2.arrowedLine(
                self.image_buffer,
                startcoord,
                endcoord,
                color,
                thickness=thickness,
                line_type=cv2.LINE_AA,
                tipLength=arrowproportion,
            )
        self.action_list.append(
            [
                "drawedgeline",
                startcoord,
                endcoord,
                color,
                edgecolor,
                thickness,
                edgethickness,
                arrowpixels,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_circle(self, center_x, center_y, rad, color=None, thickness=None):
        """Draw a circle on the image."""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawCircle: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        center_y = self.orient_height(center_y)  # Make sure HEIGHT is right way up.
        self.image_buffer = cv2.circle(
            self.image_buffer,
            (center_x, center_y),
            rad,
            color,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(
            ["drawcircle", center_x, center_y, rad, color, thickness]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_edge_circle(
        self,
        center_x,
        center_y,
        rad,
        color=None,
        thickness=None,
        edgecolor=None,
        edgethickness=1,
    ):
        """Draw a circle on the image with a colored edge."""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawCircle: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        center_y = self.orient_height(center_y)  # Make sure HEIGHT is right way up.
        self.image_buffer = cv2.circle(
            self.image_buffer,
            (center_x, center_y),
            rad,
            edgecolor,
            thickness=thickness + (2 * edgethickness),
            lineType=cv2.LINE_AA,
        )
        self.image_buffer = cv2.circle(
            self.image_buffer,
            (center_x, center_y),
            rad,
            color,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(
            ["drawedgecircle", center_x, center_y, rad, color, thickness]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def fill_circle(self, center_x, center_y, rad, color=None):
        """Fill a circle on the image."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FillCircle: No image in the buffer.")
        color = self.safe_color(color)
        center_y = self.orient_height(center_y)  # Make sure HEIGHT is right way up.
        self.image_buffer = cv2.circle(
            self.image_buffer,
            (center_x, center_y),
            rad,
            color,
            thickness=-1,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(["fillcircle", center_x, center_y, rad, color])
        self.modified_timestamp = self.now_utc()
        return True

    def set_pixel(self, center_x, center_y, color=None):
        """Set a single pixel on the image."""
        if self.image_missing():
            print("pilomarimage", self.name, ".SetPixel: No image in the buffer.")
        color = self.safe_color(color)
        center_y = self.orient_height(center_y)  # Make sure HEIGHT is right way up.
        self.image_buffer[center_y, center_x] = color
        self.action_list.append(["setpixel", center_x, center_y, color])
        self.modified_timestamp = self.now_utc()
        return True

    def get_pixel(self, center_x, center_y):
        """Return value of a single pixel on the image.
        Doesn't convert datatype!"""
        if self.image_missing():
            print("pilomarimage", self.name, ".GetPixel: No image in the buffer.")
        center_y = self.orient_height(center_y)  # Make sure HEIGHT is right way up.
        color = tuple(self.image_buffer[center_y, center_x])
        return color

    def blend_color(self, fromcolor, tocolor, ratio):
        """Find color between two values. Ratio says how much of each color to use.
        0.0 = All FROM COLOR
        1.0 = All TO COLOR"""
        ratio = min(max(ratio, 0.0), 1.0)  # Clip value.
        fromratio = ratio
        toratio = 1.0 - ratio
        gt = self.get_type()
        if gt == "grayscale":
            color = int(min(fromcolor * fromratio + tocolor * toratio), 255)
        elif gt == "bgr":
            color = (
                min(fromcolor[0] * fromratio + tocolor[0] * toratio, 255),
                min(fromcolor[1] * fromratio + tocolor[1] * toratio, 255),
                min(fromcolor[2] * fromratio + tocolor[2] * toratio, 255),
            )
        else:  # 'bgra'
            color = (
                min(fromcolor[0] * fromratio + tocolor[0] * toratio, 255),
                min(fromcolor[1] * fromratio + tocolor[1] * toratio, 255),
                min(fromcolor[2] * fromratio + tocolor[2] * toratio, 255),
                min(fromcolor[3] * fromratio + tocolor[3] * toratio, 255),
            )
        return color

    def fade_circle(self, center_x, center_y, rad, color=None, fadecolor=None):
        """Fill a circle on the image, but the color fades from center to edge"""
        if self.image_missing():
            print("pilomarimage", self.name, ".FadeCircle: No image in the buffer.")
        color = self.safe_color(color)
        center_y = self.orient_height(center_y)  # Make sure HEIGHT is right way up.
        if fadecolor is None:
            fadecolor = self.safe_color(0)  # Default to Black.
        else:
            fadecolor = self.safe_color(fadecolor)
        prevcolor = None  # Only draw circles when the color changes.
        for i in range(rad, 0, -2):
            ratio = (rad - i) / float(rad)  # Ratio is ZERO at the edge.
            gradedcolor = self.blend_color(color, fadecolor, ratio)
            if gradedcolor != prevcolor:
                self.image_buffer = cv2.circle(
                    self.image_buffer,
                    (center_x, center_y),
                    i,
                    gradedcolor,
                    thickness=-1,
                    lineType=cv2.LINE_AA,
                )
                prevcolor = gradedcolor
        self.action_list.append(
            ["fadecircle", center_x, center_y, rad, color, fadecolor]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def get_text_area(self, text, size=1.0, thickness=None):
        """Calculate the pixel area covered by a text line.
        xdim = overall pixel width.
        ydim = overall pixel height including tails of letters.
        baseline = y pixel offset to account for tails of letters."""
        (label_width, label_height), baseline = cv2.getTextSize(
            text, self.font, size, thickness
        )
        xdim = label_width
        ydim = label_height + baseline
        return xdim, ydim, baseline

    def text_boundary(
        self,
        text,
        fromx,
        fromy,
        size=1.0,
        thickness=None,
        hjust="l",
        vjust="t",
        border=None,
    ):
        """Return boundaries of a text line.
        Given a single line, this returns the two corners of the surrounding text box
        and also the next/prev starting height for any following line."""
        thickness = self.safe_thickness(thickness)
        xdim, ydim, ybase = self.get_text_area(
            text, size=size, thickness=thickness
        )  # Boundaries of the text.
        if hjust == "c":  # Center the text horizontally on the location.
            x = int(fromx - xdim / 2)
        elif hjust == "r":  # text ends horizontally at the location.
            x = int(fromx - xdim)
        else:
            x = fromx  # text starts horizontally at the location.
        if vjust == "c":  # Center the text vertically on the location.
            y = int(fromy + ydim / 2) - ybase
        elif vjust == "b":  # Text is below the location.
            y = int(fromy + ydim) - ybase
        else:
            y = fromy - ybase  # Test is above the location.
        if border is not None:
            b = border
        else:
            b = 0
        x1 = x - b
        y1 = y + ybase + b
        x2 = x + xdim + b
        y2 = y - ydim + ybase + b
        nexty = (
            fromy + ydim
        )  # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        prevy = (
            fromy - ydim
        )  # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        return x1, y1, x2, y2, nexty, prevy

    def add_text_block(
        self,
        textlines,
        fromx,
        fromy,
        color=None,
        size=1.0,
        thickness=None,
        hjust="l",
        vjust="t",
        border=None,
        bgcolor=None,
    ):
        """Take a list of text lines and paint as a block.
        Lines can be provided as a list or as a single item with newline characters inserted.

        -----------------------------------
        *Q* Justification doesn't work yet.
        -----------------------------------

        """
        thickness = self.safe_thickness(thickness)
        if type(textlines) is str:
            textlines = [textlines]  # Make sure it's a list we're handling.
        nl = []
        for line in textlines:  # Split on newline character too.
            nlines = str(line).split("\n")
            nl = nl + nlines
        textlines = nl
        minx = maxx = fromx  # Start/stop x dimensions of text block.
        miny = maxy = fromy  # Start/stop y dimensions of text block.
        for i, line in enumerate(
            textlines
        ):  # Now calculate the total size of the entire text block.
            if i == 0:  # 1st line.
                xa1, ya1, xa2, ya2, nexty, prevy = self.text_boundary(
                    line, fromx, fromy, size, thickness, hjust, vjust
                )
            else:
                xa1, ya1, xa2, ya2, nexty, prevy = self.text_boundary(
                    line, fromx, nexty, size, thickness, hjust, vjust
                )
            minx = min(minx, xa1, xa2)
            maxx = max(maxx, xa1, xa2)
            miny = min(miny, ya1, ya2)
            maxy = max(maxy, ya1, ya2)
        spanx = maxx - minx
        spany = maxy - miny
        if border is not None:
            minx = minx - border
            maxx = maxx + border
            miny = miny - border
            maxy = maxy + border
        self.fill_rectangle((minx, miny), (maxx, maxy), color=bgcolor)
        # Add border.
        if border is not None:  # Draw a border around the text.
            self.draw_rectangle(
                (minx, miny), (maxx, maxy), color=color, thickness=thickness
            )
        # Now add text.
        for i, line in enumerate(textlines):
            if (
                i == 0
            ):  # 1st line. # Take over painting of border and background to make it a block instead.
                self.add_text(
                    line,
                    fromx,
                    fromy,
                    color=color,
                    size=size,
                    thickness=thickness,
                    hjust=hjust,
                    vjust=vjust,
                    border=None,
                    bgcolor=None,
                )
            else:  # subsequent lines.
                self.add_text(
                    line,
                    fromx,
                    self.next_text_y,
                    color=color,
                    size=size,
                    thickness=thickness,
                    hjust=hjust,
                    vjust=vjust,
                    border=None,
                    bgcolor=None,
                )
        return True

    def add_text(
        self,
        text,
        fromx,
        fromy,
        color=None,
        size=1.0,
        thickness=None,
        hjust="l",
        vjust="t",
        border=None,
        bgcolor=None,
    ):
        """Add text to an image.
        vjust = vertical justification. 'bottom','center','top'
                bottom = text is 'below' the location.

                                *
                                  Text

                center = text is 'beside' the location.

                                * Text
                top = text is 'above' the location.

                                  Text
                                *

        hjust = horizontal justification. 'left','center','right'
                left = text starts at the location.

                                *
                                  Text

                center = text spread across the location.

                                *
                               Text

                right = text ends at the location.

                                *
                           Text

        bgcolor = color of background for the text. If missing, no background is generated.

        border = draw a border. Value is the spacing between the letters and the border.

        If you want to create a block of text, use self.next_text_y and self.prev_text_y to find the
        y co-ordinate of the next/prev line of text to generate. This takes font size into account.

            self.add_text('line1',x,y) # Print line 1 as usual.
            self.add_text('line2',x,self.next_text_y) # NextTextY contains the starting Y coordinate for the next line.

        If you are changing font sizes, it is best to work bottom-up using self.prev_text_y, the spacing works more dynamically this way.

            self.add_text('lastline',x,y,size=1) # Print last line as usual.
            self.add_text('prevline',x,self.prev_text_y,size=2) # Print previous (higher) line next.


        *Q* TODO: OpenCV only supports basic 127 ASCII characters, to add UNICODE etc convert to PIL,
            add the extended characters there, then convert back.
        """
        if self.image_missing():
            print("pilomarimage", self.name, ".AddText: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        xdim, ydim, ybase = self.get_text_area(
            text, size=size, thickness=thickness
        )  # Boundaries of the text.
        if hjust == "c":  # Center the text horizontally on the location.
            x = int(fromx - xdim / 2)
        elif hjust == "r":  # text ends horizontally at the location.
            x = int(fromx - xdim)
        else:
            x = fromx  # text starts horizontally at the location.
        if vjust == "c":  # Center the text vertically on the location.
            y = int(fromy + ydim / 2) - ybase
        elif vjust == "b":  # Text is below the location.
            y = int(fromy + ydim) - ybase
        else:
            y = fromy - ybase  # Test is above the location.
        if border is not None:
            b = border
        else:
            b = 0
        if self.text_collision(
            x - b, y + ybase + b, x + xdim + b, y - ydim + ybase - b
        ):  # This would collide with existing text, so don't add it.
            OK2Draw = False  # It's not safe to draw.
        else:
            OK2Draw = True  # It's safe to draw.
        if OK2Draw:  # Proceed with the drawing.
            if bgcolor is not None:  # Draw background under the text.
                bgcolor = self.safe_color(bgcolor)
                self.fill_rectangle(
                    (x - b, y + ybase + b),
                    (x + xdim + b, y - ydim + ybase - b),
                    color=bgcolor,
                )
            # We're OK to add the text at this point.
            if border is not None:  # Draw a border around the text.
                self.draw_rectangle(
                    (x - border, y + ybase + border),
                    (x + xdim + border, y - ydim + ybase - border),
                    color=color,
                    thickness=thickness,
                )
            # Store where the 'next' line of text would go if we're printing multiple lines. (Text must remain same size!)
            self.image_buffer = cv2.putText(
                self.image_buffer,
                text,
                self.orient_coord((x, y)),
                self.font,
                size,
                color,
                thickness,
                lineType=cv2.LINE_AA,
            )
            self.action_list.append(
                ["addtext", text, fromx, fromy, color, size, thickness, hjust, vjust]
            )
            self.modified_timestamp = self.now_utc()
        self.next_text_x = fromx  # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.next_text_y = (
            fromy + ydim + 1
        )  # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.prev_text_x = fromx  # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        self.prev_text_y = (
            fromy - ydim - 1
        )  # If printing multiple lines of text, this is the start point for the previous line if you're printing upwards.
        return True

    def add_angle_text(
        self,
        text,
        fromx,
        fromy,
        color=None,
        size=1.0,
        thickness=None,
        hjust="l",
        vjust="t",
        border=None,
        bgcolor=None,
        angle=90,
    ):
        """Add text to an image at an angle from horizontal.

        This is very limited functionality. OpenCV text handling is very basic, it is primarily there for development/debugging support
        with image analysis tasks - which is OpenCV's primary purpose. Adding complexity to it creates a big overhead, but if you REALLY
        need the occasional angled text, this is the place to create it.

        *Q* A future version could perhaps switch this to PIL handling, which may have more facilities. To be checked.

        vjust = vertical justification. 'bottom','center','top'
                bottom = text is 'below' the location.

                                *
                                  Text

                center = text is 'beside' the location.

                                * Text
                top = text is 'above' the location.

                                  Text
                                *

        hjust = horizontal justification. 'left','center','right'
                left = text starts at the location.

                                *
                                  Text

                center = text spread across the location.

                                *
                               Text

                right = text ends at the location.

                                *
                           Text

        bgcolor = color of background for the text. If missing, no background is generated.

        border = draw a border. Value is the spacing between the letters and the border.

        If you want to create a block of text, use self.next_text_y and self.prev_text_y to find the
        y co-ordinate of the next/prev line of text to generate. This takes font size into account.

            self.add_text('line1',x,y) # Print line 1 as usual.
            self.add_text('line2',x,self.next_text_y) # NextTextY contains the starting Y coordinate for the next line.

        If you are changing font sizes, it is best to work bottom-up using self.prev_text_y, the spacing works more dynamically this way.

            self.add_text('lastline',x,y,size=1) # Print last line as usual.
            self.add_text('prevline',x,self.prev_text_y,size=2) # Print previous (higher) line next.

        angle = 0 (No rotation), 90 (clockwise 90Deg), 180 (rotate 180deg) and 270 (anticlockwise 90deg).
        - Other angles will give unpredictable results.

        To achieve this, the image is rotated, the text is added, then the image is returned to original orientation.

        *Q* STILL UNDER DEVELOPMENT. NOT FINISHED YET.
            ONLY SUPPORTS 90DEGREE ANGLE SO FAR.

        NOTE: This is SLOW!!"""
        angle = angle % 360
        supportedangles = [0, 90]  # Which angles are supported?
        if not angle in supportedangles:
            print(
                "pilomarimage.AddAngleText() only supports these angles",
                str(supportedangles),
            )
            return False
        if self.image_missing():
            print("pilomarimage", self.name, ".AddAngleText: No image in the buffer.")
        fromx = int(fromx)
        fromy = int(
            self.orient_height(fromy)
        )  # Handle vertical orientation of pixel address here. Then it's simpler for all the following maths.
        if angle == 90:
            # 1st rotate the image to accept the text. Opposite direction to the text angle!
            self.rotate_image(360 - angle)
            # Translate rotated vector to new co-ordinates based upon new dimensions.
            fromx, fromy = self.rotate_coordinates(
                fromx, fromy, 360 - angle
            )  # We counterrotated the image so that the text is written at the desired angle, so counterrotate the text coordinates too.
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        xdim, ydim, ybase = self.get_text_area(
            text, size=size, thickness=thickness
        )  # Boundaries of the text.
        # Establish x,y as the actual co-ordinates at which to print the text in order to achieve justification.
        if angle == 90:
            # With a 90 degree rotation the justification instructions must rotate too. Swap hjust and vjust appropriately.
            if (
                vjust == "c"
            ):  # hjust == 'c': # Center the text horizontally on the location.
                x = int(fromx - xdim / 2)
            elif (
                vjust == "t"
            ):  # hjust == 'r': # text ends horizontally at the location.
                x = int(fromx - xdim)
            else:
                x = fromx  # text starts horizontally at the location.
            if (
                hjust == "c"
            ):  # vjust == 'c': # Center the text vertically on the location.
                y = int(fromy + ydim / 2) - ybase
            elif hjust == "l":  # vjust == 'b': # Text is below the location.
                y = int(fromy + ydim) - ybase
            else:
                y = fromy - ybase  # Test is above the location.
        else:
            if hjust == "c":  # Center the text horizontally on the location.
                x = int(fromx - xdim / 2)
            elif hjust == "r":  # text ends horizontally at the location.
                x = int(fromx - xdim)
            else:
                x = fromx  # text starts horizontally at the location.
            if vjust == "c":  # Center the text vertically on the location.
                y = int(fromy + ydim / 2) - ybase
            elif vjust == "b":  # Text is below the location.
                y = int(fromy + ydim) - ybase
            else:
                y = fromy - ybase  # Test is above the location.
        if bgcolor is not None:  # Draw background under the text.
            bgcolor = self.safe_color(bgcolor)
            if border is not None:
                b = border
            else:
                b = 0
            self.fill_rectangle(
                (x - b, y + ybase + b),
                (x + xdim + b, y - ydim + ybase + b),
                color=bgcolor,
            )
        if border is not None:  # Draw a border around the text.
            self.draw_rectangle(
                (x - border, y + ybase + border),
                (x + xdim + border, y - ydim + ybase + border),
                color=color,
                thickness=thickness,
            )
        self.image_buffer = cv2.putText(
            self.image_buffer,
            text,
            (x, y),
            self.font,
            size,
            color,
            thickness,
            lineType=cv2.LINE_AA,
        )  # *Q* <- Not implemented for angled text yet.
        # Store where the 'next' line of text would go if we're printing multiple lines. (Text must remain same size!)
        if angle == 90:
            # Now turn image the right way round again.
            self.rotate_image(angle)
        self.action_list.append(
            [
                "addangletext",
                text,
                fromx,
                fromy,
                color,
                size,
                thickness,
                hjust,
                vjust,
                angle,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def add_edge_text(
        self,
        text,
        fromx,
        fromy,
        color=None,
        edgecolor=None,
        size=1.0,
        thickness=None,
        edgethickness=None,
        hjust="l",
        vjust="t",
        border=None,
        bgcolor=None,
    ):
        """Add text to an image with an outline around it.
        vjust = vertical justification. 'bottom','center','top'
                bottom = text is 'below' the location.

                                *
                                  Text

                center = text is 'beside' the location.

                                * Text
                top = text is 'above' the location.

                                  Text
                                *

        hjust = horizontal justification. 'left','center','right'
                left = text starts at the location.

                                *
                                  Text

                center = text spread across the location.

                                *
                               Text

                right = text ends at the location.

                                *
                           Text

        bgcolor = color of background for the text. If missing, no background is generated.

        border = draw a border. Value is the spacing between the letters and the border.

        If you want to create a block of text, use self.next_text_y and self.prev_text_y to find the
        y co-ordinate of the next/prev line of text to generate. This takes font size into account.

            self.add_text('line1',x,y) # Print line 1 as usual.
            self.add_text('line2',x,self.next_text_y) # NextTextY contains the starting Y coordinate for the next line.

        If you are changing font sizes, it is best to work bottom-up using self.prev_text_y, the spacing works more dynamically this way.

            self.add_text('lastline',x,y,size=1) # Print last line as usual.
            self.add_text('prevline',x,self.prev_text_y,size=2) # Print previous (higher) line next.

        """
        if self.image_missing():
            print("pilomarimage", self.name, ".AddEdgeText: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        if edgethickness is None:
            edgethickness = 1  # center thickness + 1 pixel either side.
        color = self.safe_color(color)
        xdim, ydim, ybase = self.get_text_area(
            text, size=size, thickness=int(thickness + (2 * edgethickness))
        )  # Boundaries of the text.
        edgecolor = self.safe_color(edgecolor)
        if hjust == "c":  # Center the text horizontally on the location.
            x = int(fromx - xdim / 2)
        elif hjust == "r":  # text ends horizontally at the location.
            x = int(fromx - xdim)
        else:
            x = fromx  # text starts horizontally at the location.
        if vjust == "c":  # Center the text vertically on the location.
            y = int(fromy + ydim / 2) - ybase
        elif vjust == "b":  # Text is below the location.
            y = int(fromy + ydim) - ybase
        else:
            y = fromy - ybase  # Test is above the location.
        if bgcolor is not None:  # Draw background under the text.
            bgcolor = self.safe_color(bgcolor)
            if border is not None:
                b = border
            else:
                b = 0
            self.fill_rectangle(
                (x - b, y + ybase + b),
                (x + xdim + b, y - ydim + ybase + b),
                color=bgcolor,
            )
        if border is not None:  # Draw a border around the text.
            self.draw_rectangle(
                (x - border, y + ybase + border),
                (x + xdim + border, y - ydim + ybase + border),
                color=edgecolor,
                thickness=edgethickness,
            )
            self.draw_rectangle(
                (x - border, y + ybase + border),
                (x + xdim + border, y - ydim + ybase + border),
                color=color,
                thickness=thickness,
            )
        self.image_buffer = cv2.putText(
            self.image_buffer,
            text,
            self.orient_coord((x, y)),
            self.font,
            size,
            edgecolor,
            int(thickness + (2 * edgethickness)),
            lineType=cv2.LINE_AA,
        )
        self.image_buffer = cv2.putText(
            self.image_buffer,
            text,
            self.orient_coord((x, y)),
            self.font,
            size,
            color,
            thickness,
            lineType=cv2.LINE_AA,
        )
        # Store where the 'next' line of text would go if we're printing multiple lines. (Text must remain same size!)
        self.next_text_x = fromx  # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.next_text_y = (
            fromy + ydim
        )  # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.prev_text_x = fromx  # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        self.prev_text_y = (
            fromy - ydim
        )  # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        self.action_list.append(
            ["addedgetext", text, fromx, fromy, color, size, thickness]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_polygon(self, pointlist, color=None, thickness=None):
        """Draw polygon.
        pointlist is a list of (x,y) tuples."""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawPolygon: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        # *Q* OrientCoord() to do.
        cv2.drawPoly(
            self.image_buffer, np.array([pointlist]), color=color, thickness=thickness
        )
        self.action_list.append(["drawpolygon", pointlist, color, thickness])
        self.modified_timestamp = self.now_utc()
        return True

    def draw_edge_polygon(
        self, pointlist, color=None, edgecolor=None, thickness=None, edgethickness=None
    ):
        """Draw polygon.
        pointlist is a list of (x,y) tuples."""
        if self.image_missing():
            print(
                'pilomarimage",self.name,' ".DrawEdgePolygon: No image in the buffer."
            )
        thickness = self.safe_thickness(thickness)
        if edgethickness is None:
            edgethickness = 1  # center thickness + 1 pixel either side.
        color = self.safe_color(color)
        edgecolor = self.safe_color(edgecolor)
        # *Q* OrientCoord() to do.
        cv2.drawPoly(
            self.image_buffer,
            np.array([pointlist]),
            color=edgecolor,
            thickness=int(thickness + (2 * edgethickness)),
        )
        cv2.drawPoly(
            self.image_buffer, np.array([pointlist]), color=color, thickness=thickness
        )
        self.action_list.append(
            ["drawedgepolygon", pointlist, color, edgecolor, thickness, edgethickness]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def fill_polygon(self, pointlist, color=None):
        """Draw filled polygon.
        pointlist is a list of (x,y) tuples."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FillPolygon: No image in the buffer.")
        color = self.safe_color(color)
        # *Q* OrientCoord() to do.
        cv2.fillPoly(self.image_buffer, np.array([pointlist]), color=color)
        self.action_list.append(["fillpolygon", pointlist, color])
        self.modified_timestamp = self.now_utc()
        return True

    def draw_rectangle(self, startcoord, endcoord, color=None, thickness=None):
        """Draw a Rectangle on the image."""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawRectangle: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        startcoord = self.orient_coord(startcoord)  # Get height right way up.
        endcoord = self.orient_coord(endcoord)  # Get height right way up.
        self.image_buffer = cv2.rectangle(
            self.image_buffer, startcoord, endcoord, color, thickness
        )
        self.action_list.append(
            ["drawrectangle", startcoord, endcoord, color, thickness]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def fill_rectangle(self, startcoord, endcoord, color=None):
        """Draw a filled Rectangle on the image."""
        if self.image_missing():
            print("pilomarimage", self.name, ".FillRectangle: No image in the buffer.")
        color = self.safe_color(color)
        startcoord = self.orient_coord(startcoord)  # Get height right way up.
        endcoord = self.orient_coord(endcoord)  # Get height right way up.
        self.image_buffer = cv2.rectangle(
            self.image_buffer, startcoord, endcoord, color, thickness=-1
        )
        self.action_list.append(["fillrectangle", startcoord, endcoord, color])
        self.modified_timestamp = self.now_utc()
        return True

    def fade_rectangle(self, startcoord, endcoord, color=None, fadecolor=None):
        """Fill a ractangle on the image, but the color fades from center to edge"""
        if self.image_missing():
            print("pilomarimage", self.name, ".FadeRectangle: No image in the buffer.")
        color = self.safe_color(color)
        if fadecolor is None:
            fadecolor = self.safe_color(0)  # Default to Black.
        else:
            fadecolor = self.safe_color(fadecolor)
        prevcolor = None  # Only draw rectangles when the color changes.
        side_x = endcoord[0] - startcoord[0]
        side_y = endcoord[1] - startcoord[1]
        center_x = int((endcoord[0] + startcoord[0]) / 2)
        center_y = int((endcoord[1] + startcoord[1]) / 2)
        rad = max(abs(side_x), abs(side_y))
        for i in range(rad, 0, -4):
            colorratio = (rad - i) / float(rad)  # Ratio is ZERO at the edge.
            sizeratio = i / float(rad)
            gradedcolor = self.blend_color(color, fadecolor, colorratio)
            if gradedcolor != prevcolor:
                startcoord = (
                    int(center_x - (side_x * sizeratio / 2)),
                    int(center_y - (side_y * sizeratio / 2)),
                )
                endcoord = (
                    int(center_x + (side_x * sizeratio / 2)),
                    int(center_y + (side_y * sizeratio / 2)),
                )
                startcoord = self.orient_coord(startcoord)  # Get height right way up.
                endcoord = self.orient_coord(endcoord)  # Get height right way up.
                self.image_buffer = cv2.rectangle(
                    self.image_buffer, startcoord, endcoord, gradedcolor, thickness=-1
                )
                prevcolor = gradedcolor
        self.action_list.append(
            ["faderectangle", startcoord, endcoord, color, fadecolor]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_ellipse(
        self,
        center_x,
        center_y,
        axis_x,
        axis_y,
        angle=0,
        startAngle=0,
        endAngle=360,
        color=None,
        thickness=None,
    ):
        """Draw an ellipse on the image.
        center_coordinates = (x,y)
        axeslength = (a,b)
        angle = 0-360
        startAngle = 0-360
        endAngle = 0-360"""
        if self.image_missing():
            print("pilomarimage", self.name, ".DrawEllipse: No image in the buffer.")
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
        center_y = self.orient_height(center_y)
        # *Q* OrientHeight needs to switch angles too.
        self.image_buffer = cv2.ellipse(
            self.image_buffer,
            (int(center_x), int(center_y)),
            (int(axis_x), int(axis_y)),
            int(angle),
            int(startAngle),
            int(endAngle),
            color,
            thickness,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(
            [
                "drawellipse",
                center_x,
                center_y,
                axis_x,
                axis_y,
                angle,
                startAngle,
                endAngle,
                color,
                thickness,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_edge_ellipse(
        self,
        center_x,
        center_y,
        axis_x,
        axis_y,
        angle=0,
        startAngle=0,
        endAngle=360,
        color=None,
        edgecolor=None,
        thickness=None,
        edgethickness=1,
    ):
        """Draw an ellipse on the image.
        center_coordinates = (x,y)
        axeslength = (a,b)
        angle = 0-360
        startAngle = 0-360
        endAngle = 0-360"""
        if self.image_missing():
            print(
                "pilomarimage", self.name, ".DrawEdgeEllipse: No image in the buffer."
            )
        thickness = self.safe_thickness(thickness)
        color = self.safe_color(color)
        edgethickness = self.safe_thickness(edgethickness)
        edgecolor = self.safe_color(edgecolor)
        # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
        center_y = self.orient_height(center_y)
        # *Q* OrientHeight needs to switch angles too.
        self.image_buffer = cv2.ellipse(
            self.image_buffer,
            (int(center_x), int(center_y)),
            (int(axis_x), int(axis_y)),
            int(angle),
            int(startAngle),
            int(endAngle),
            edgecolor,
            (thickness + 2 * edgethickness),
            lineType=cv2.LINE_AA,
        )
        self.image_buffer = cv2.ellipse(
            self.image_buffer,
            (int(center_x), int(center_y)),
            (int(axis_x), int(axis_y)),
            int(angle),
            int(startAngle),
            int(endAngle),
            color,
            thickness,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(
            [
                "drawedgeellipse",
                center_x,
                center_y,
                axis_x,
                axis_y,
                angle,
                startAngle,
                endAngle,
                color,
                thickness,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def fill_ellipse(
        self,
        center_x,
        center_y,
        axis_x,
        axis_y,
        angle=0,
        startAngle=0,
        endAngle=360,
        color=None,
    ):
        """Draw an ellipse on the image.
        center_coordinates = (x,y)
        axeslength = (a,b)
        angle = 0-360
        startAngle = 0-360
        endAngle = 0-360"""
        if self.image_missing():
            print("pilomarimage", self.name, ".FillEllipse: No image in the buffer.")
        color = self.safe_color(color)
        center_y = self.orient_height(center_y)
        # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
        self.image_buffer = cv2.ellipse(
            self.image_buffer,
            (int(center_x), int(center_y)),
            (int(axis_x), int(axis_y)),
            int(angle),
            int(startAngle),
            int(endAngle),
            color,
            thickness=-1,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(
            [
                "fillellipse",
                center_x,
                center_y,
                axis_x,
                axis_y,
                angle,
                startAngle,
                endAngle,
                color,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def fade_ellipse(
        self,
        center_x,
        center_y,
        axis_x,
        axis_y,
        angle=0,
        startAngle=0,
        endAngle=360,
        color=None,
        fadecolor=None,
    ):
        """Fill an ellipse on the image, but the color fades from center to edge"""
        if self.image_missing():
            print("pilomarimage", self.name, ".FadeEllipse: No image in the buffer.")
            self.log(
                "pilomarimage",
                self.name,
                ".FadeEllipse: No image in the buffer.",
                level="error",
                terminal=True,
            )

        color = self.safe_color(color)
        if fadecolor is None:
            fadecolor = self.safe_color(0)  # Default to Black.
        else:
            fadecolor = self.safe_color(fadecolor)
        prevcolor = None  # Only draw ellipses when the color changes.
        rad = max(axis_x, axis_y)
        for i in range(rad, 0, -2):
            colorratio = (rad - i) / float(rad)  # Ratio is ZERO at the edge.
            sizeratio = i / float(rad)
            gradedcolor = self.blend_color(color, fadecolor, colorratio)
            if gradedcolor != prevcolor:
                # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
                xt = int(axis_x * sizeratio)
                yt = int(axis_y * sizeratio)
                center_y = self.orient_height(center_y)
                self.image_buffer = cv2.ellipse(
                    self.image_buffer,
                    (int(center_x), int(center_y)),
                    (xt, yt),
                    int(angle),
                    int(startAngle),
                    int(endAngle),
                    gradedcolor,
                    thickness=-1,
                    lineType=cv2.LINE_AA,
                )
                prevcolor = gradedcolor
        self.action_list.append(
            [
                "fadeellipse",
                center_x,
                center_y,
                axis_x,
                axis_y,
                angle,
                startAngle,
                endAngle,
                color,
                fadecolor,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True

    def draw_dumbbell(
        self,
        drawfrom,
        drawto,
        rad,
        fromcolor,
        tocolor,
        linecolor,
        arrow,
        thickness=None,
    ):
        """Add a 'dumbbell' to an image between two different points.

        from = tuple (x,y)
        to = tuple (x,y)
        fromcolor = tuple (b,g,r,a)
        tocolor = tuple (b,g,r,a)
        linecolor = tuple (b,g,r,a)
        arrow = boolean 6

          xxx                     .    xxx
         x   x                     .  x   x
        x     x                     .x     x
        x  O  x----------------------x  o  x
        x     x                     .x     x
         x   x                     .  x   x
          xxx                     .    xxx"""

        if self.image_missing():
            print("pilomarimage", self.name, ".DrawDumbbell: No image in the buffer.")
            self.log(
                "pilomarimage",
                self.name,
                ".DrawDumbbell: No image in the buffer.",
                level="error",
                terminal=True,
            )
        drawfrom = self.orient_coord(drawfrom)  # Get height right way around.
        drawto = self.orient_coord(drawto)
        fromx = drawfrom[0]  # center of the FROM circle.
        fromy = drawfrom[1]
        tox = drawto[0]  # center of the TO circle.
        toy = drawto[1]
        fromcolor = self.safe_color(fromcolor)
        tocolor = self.safe_color(tocolor)
        linecolor = self.safe_color(linecolor)
        thickness = self.safe_thickness(thickness)
        # Calculate distance between FROM and TO points.
        dx = tox - fromx
        dy = toy - fromy
        distance = math.sqrt((dx**2) + (dy**2))
        angle = math.atan2(dy, dx)  # What angle is the joining line at?
        # Line does not cross the boundary circle drawn around each point.
        # Calculate the points on the circumference of each circle that the arrowed line will start and end on.
        rc = rad * math.cos(angle)  # x offset for circle edge where line starts.
        rs = rad * math.sin(angle)  # y offset for circle edge where line starts.
        startx = int(fromx + rc)  # Draw line from this point on the starting circle.
        starty = int(fromy + rs)
        endx = int(tox - rc)  # Draw line to this point on the ending circle.
        endy = int(toy - rs)
        dia = (
            rad * 2
        )  # Only draw the line if there's a big enough gap between the two circles.
        if distance > dia:  # Enough space to draw a line.
            arrowproportion = 10.0 / (
                distance - dia
            )  # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
            if arrow:
                self.image_buffer = cv2.arrowedLine(
                    self.image_buffer,
                    (startx, starty),
                    (endx, endy),
                    linecolor,
                    thickness=thickness,
                    line_type=cv2.LINE_AA,
                    tipLength=arrowproportion,
                )
            else:
                self.image_buffer = cv2.line(
                    self.image_buffer,
                    (startx, starty),
                    (endx, endy),
                    linecolor,
                    thickness=thickness,
                    lineType=cv2.LINE_AA,
                )
        self.image_buffer = cv2.circle(
            self.image_buffer,
            (fromx, fromy),
            rad,
            fromcolor,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
        self.image_buffer = cv2.circle(
            self.image_buffer,
            (tox, toy),
            rad,
            tocolor,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
        self.action_list.append(
            [
                "drawdumbbell",
                drawfrom,
                drawto,
                rad,
                fromcolor,
                tocolor,
                linecolor,
                arrow,
                thickness,
            ]
        )
        self.modified_timestamp = self.now_utc()
        return True  # The image now has the 'dumbbell' drawn on it.

    def brightness_histogram(self):
        """Return array of brightness levels.
        Uses a grayscale representation of the current image to calculate the brightness.
        Returns an integer list of 256 entries, each entry is the number of pixels of that brightness.
        """
        tempbuffer = self.new_buffer_type(
            "grayscale"
        )  # Create grayscale copy of the buffer.
        hist = cv2.calcHist([tempbuffer], [0], None, [256], [0, 256])
        return hist

    def weighted_brightness(self):
        """For the current image, calculate the brightness histogram and return the weighted brightness of the image.
        Returns a value in the range 0-255 indicating the weighted average brightness of all the pixels in the image.
        """
        weightedtotal = 0
        pixeltotal = self.get_width() * self.get_height()
        for pixelvalue, pixelcount in enumerate(self.brightness_histogram()):
            weightedtotal += (
                pixelvalue + 1
            ) * pixelcount  # Add 1 to pixelvalue so that '0' brightness pixels still count.
        wb = (
            round(weightedtotal / pixeltotal, 0) - 1
        )  # Calculate weighted average, but subtract 1 to return '0' brightness pixels within range again.
        return wb

    def describe_image(self):
        """Print information about the current image buffer."""
        print("Describe image:")
        print("Name:", self.name)
        print("Created:", self.created_timestamp, "Modified:", self.modified_timestamp)
        if self.image_exists():
            print("Shape:", self.image_buffer.shape)
        else:
            print("image_buffer is empty")
        print("Type:", self.get_type())
        michelson_contrast, stddev_contrast = self.measure_contrast()
        print(
            "Michelson contrast:",
            michelson_contrast,
            "STD DEV contrast:",
            stddev_contrast,
        )
        print("Sharpness:", self.sharpness())
        print("Pen: Color:", self.pen_color, "Thickness:", self.pen_thickness)
        print("ActionList:", self.action_list)


class pilomarkeogram:
    """Simple keogram builder.
    Usage
    MyKeo = pilomarkeogram('keogram',widthpixels,heightpixels)
    MyKeo.Extract(imagehandler1)
    MyKeo.Extract(imagehandler2)
    MyKeo.Extract(imagehandler3)
    MyKeo.Extract(imagehandler4)
    MyKeo.BuildImageBuffer()
    ... you can now manipulate/markup the MyKeo.Keogram image instance.
    MyKeo.save_file('keogram.jpg')
    """

    def __init__(self, name, width, height):
        self.name = name  # A name for this instance.
        self.width = width  # Width of target image.
        self.height = height  # Height of target image.
        self.keogram_pixels = None  # List of data sampled.
        self.sample_count = 0  # How many sample strips have we captured.
        self.keogram = PilomarImage(
            name="keogram", logger=None
        )  # Create a pilomarimage instance for the resulting keogram.

    def extract(self, imagehandler):  # Extract data for a keogram.
        """Extract data for a Keogram.
        imagehandler is an instance of pilomarimage containing the latest live image.
        Extracts a vertical band from each image received,
        Finds the brightest pixel in each row,
        Appends these brightest pixels to the data set from all images."""
        source_width = imagehandler.GetWidth()
        source_height = imagehandler.GetHeight()
        band = int(source_width * 0.10)  # Take middle 10% of image.
        workbuf = imagehandler.image_buffer.copy()  # Grab a copy of the light buffer.
        xstart = int((source_width - band) / 2)  # Left side of the sample band.
        xend = int((source_width + band) / 2)  # Right side of the sample band.
        workbuf = workbuf[:, xstart:xend, :]  # Extract sample band.
        gray_image = cv2.cvtColor(workbuf, cv2.COLOR_BGR2GRAY)  # Convert to grayscale
        n_width = workbuf.shape[1]  # New width of the band.
        column = []  # Empty column of pixel data we are about to extract.
        for r in range(source_height):  # Process each row of the sample in turn.
            max_brightness = 0  # Location of the brightest pixel.
            max_pixel = [0, 0, 0]  # Color of the brightest pixel.
            for c in range(n_width):  # Check each column in turn.
                brightness = gray_image[r][
                    c
                ]  # Brightness is the pixel value from the grayscale image.
                if brightness > max_brightness:  # We have a new maximum value.
                    max_brightness = brightness  # Record the new maximum.
                    max_pixel = workbuf[
                        r, c, :
                    ]  # Record the actual BGR vales for that pixel.
            column.append(
                [[max_pixel[0], max_pixel[1], max_pixel[2]]]
            )  # Add the pixel value to the values for this column.
        if type(self.keogram_pixels) == type(
            None
        ):  # No pre-existing pixel data. Create it now.
            self.keogram_pixels = np.array(column).astype(
                np.uint8
            )  # Create a single column image in Numpy.
        else:
            self.keogram_pixels = np.append(
                self.keogram_pixels, column, axis=1
            )  # Add a new column to existing image in Numpy.
        self.sample_count += 1  # Increment count of samples.

    def build_image_buffer(self):
        """ """
        writebuffer = cv2.resize(
            self.keogram_pixels, (self.width, self.height), interpolation=cv2.INTER_AREA
        )
        self.keogram.load_buffer(writebuffer)

    def save_file(self, filename):
        """Export and save the keogram data as a .jpg file on disc."""
        self.keogram.save_file(
            filename
        )  # imwrite doesn't report errors very well, beware.


if __name__ == "__main__":
    pi = PilomarImage()
