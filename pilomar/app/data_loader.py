#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data loader module for the Pilomar application.

This module handles loading and caching of various astronomical catalogs:
- Hipparcos star catalog
- Messier objects
- NGC (New General Catalog) galaxies and nebulae
- Comet orbits from Minor Planet Center
- Meteor shower information
- Constellation patterns from Stellarium

All catalogs are loaded lazily and cached for performance.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas


@dataclass
class CatalogPaths:
    """Configuration for catalog file paths."""
    data_dir: str
    star_names: str = ""
    messier: str = ""
    meteors: str = ""
    ngc: str = ""
    hipparcos_cache: str = ""
    ngc_cache: str = ""
    hipparcos_source: str = ""
    
    def __post_init__(self):
        """Initialize paths relative to data directory."""
        if not self.star_names:
            self.star_names = os.path.join(self.data_dir, "starnames.json")
        if not self.messier:
            self.messier = os.path.join(self.data_dir, "messierobjects.json")
        if not self.meteors:
            self.meteors = os.path.join(self.data_dir, "meteors.json")
        if not self.ngc:
            self.ngc = os.path.join(self.data_dir, "ngc.json")
        if not self.hipparcos_cache:
            self.hipparcos_cache = os.path.join(self.data_dir, "hipparcos.pkl")
        if not self.ngc_cache:
            self.ngc_cache = os.path.join(self.data_dir, "ngc.pkl")
        if not self.hipparcos_source:
            self.hipparcos_source = os.path.join(self.data_dir, "hip_main.dat.gz")


@dataclass
class CatalogData:
    """Container for loaded catalog data."""
    star_names: Dict[str, Dict] = field(default_factory=dict)
    messier: Dict[str, Dict] = field(default_factory=dict)
    meteors: Dict[str, Dict] = field(default_factory=dict)
    hipparcos_df: Optional[pandas.DataFrame] = None
    ngc_df: Optional[pandas.DataFrame] = None
    comets_df: Optional[pandas.DataFrame] = None
    constellation_links: List[List[str]] = field(default_factory=list)
    constellation_names: Dict[str, str] = field(default_factory=dict)
    constellation_stars: List[str] = field(default_factory=list)
    planets: Optional[Any] = None  # Skyfield ephemeris
    

class CatalogLoader:
    """Handles loading and caching of astronomical catalogs."""
    
    # NGC object type descriptions
    NGC_TYPES = {
        "aster": "Asterism",
        "brtnb": "Bright nebula",
        "cl+nb": "Cluster with nebulosity",
        "drknb": "Dark nebula",
        "galcl": "Galaxy cluster",
        "galxy": "Galaxy",
        "glocl": "Globular cluster",
        "gx+dn": "Diffuse nebula in a galaxy",
        "gx+gc": "Globular cluster in a galaxy",
        "g+c+n": "Cluster with nebulosity in a galaxy",
        "lmccn": "LMC cluster with nebulosity",
        "lmcdn": "LMC diffuse nebula",
        "lmcgc": "LMC globular cluster",
        "lmcoc": "LMC open cluster",
        "nonex": "Nonexistent",
        "opncl": "Open cluster",
        "plnnb": "Planetary nebula",
        "smccn": "SMC cluster with nebulosity",
        "smcdn": "SMC diffuse nebula",
        "smcgc": "SMC globular cluster",
        "smcoc": "SMC open cluster",
        "snrem": "Supernova remnant",
        "quasr": "Quasar",
        "1star": "Star",
        "2star": "2 Stars",
        "3star": "3 Stars",
        "4star": "4 Stars",
        "5star": "5 Stars",
        "6star": "6 Stars",
        "7star": "7 Stars",
    }
    
    def __init__(
        self,
        paths: CatalogPaths,
        logger: Optional[Any] = None,
        skyfield_loader: Optional[Any] = None
    ):
        """Initialize catalog loader.
        
        Args:
            paths: Configuration for file paths
            logger: Optional logger for messages
            skyfield_loader: Skyfield Loader object for downloading/caching
        """
        self.paths = paths
        self.logger = logger
        self.skyfield_loader = skyfield_loader
        self.data = CatalogData()
        
    def _log(self, *args, level: str = 'info', terminal: bool = False):
        """Log a message if logger is available."""
        if self.logger:
            self.logger.Log(*args, level=level, terminal=terminal)
    
    @staticmethod
    def load_json(filename: str) -> Dict:
        """Load a JSON file as a Python dictionary.
        
        Args:
            filename: Path to JSON file
            
        Returns:
            Dictionary from JSON, or empty dict if file doesn't exist
        """
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {}
    
    def load_star_names(self) -> Dict[str, Dict]:
        """Load star name dictionary (HIP number -> name, constellation)."""
        if not self.data.star_names:
            self._log("Loading star names from", self.paths.star_names, terminal=False)
            self.data.star_names = self.load_json(self.paths.star_names)
        return self.data.star_names
    
    def load_messier(self) -> Dict[str, Dict]:
        """Load and process Messier object catalog.
        
        Returns:
            Dictionary of Messier objects with computed fields
        """
        if not self.data.messier:
            self._log('Loading Messier catalog from', self.paths.messier, terminal=True)
            messier = self.load_json(self.paths.messier)
            
            # Add computed fields
            for key, obj in messier.items():
                self._process_messier_entry(obj)
            
            self.data.messier = messier
        return self.data.messier
    
    def _process_messier_entry(self, entry: Dict) -> None:
        """Add computed fields to a Messier catalog entry."""
        # Right Ascension
        ra_h = entry['ra'][0]
        ra_m = entry['ra'][1]
        ra_s = entry['ra'][2]
        entry['rah'] = ra_h
        entry['ram'] = ra_m
        entry['ras'] = ra_s
        entry['radeg'] = self._hms_to_angle(ra_h, ra_m, ra_s)
        
        # Declination
        dec_d = entry['dec'][0]
        dec_m = entry['dec'][1]
        dec_s = entry['dec'][2]
        entry['ded'] = dec_d
        entry['dem'] = dec_m
        entry['des'] = dec_s
        entry['decdeg'] = self._dms_to_angle(dec_d, dec_m, dec_s)
        
        # Labels
        entry['ralabel'] = f"{int(ra_h)}h {int(ra_m)}m {round(ra_s, 1)}s"
        entry['declabel'] = f"{int(dec_d)}d {int(dec_m)}' {round(dec_s, 1)}\""
        
        # Size in degrees
        entry['widthdeg'] = float(entry.get('width', 1)) / 60
        entry['heightdeg'] = float(entry.get('height', 1)) / 60
    
    def load_meteors(self) -> Dict[str, Dict]:
        """Load meteor shower catalog."""
        if not self.data.meteors:
            self._log('Loading meteor showers from', self.paths.meteors, terminal=True)
            self.data.meteors = self.load_json(self.paths.meteors)
        return self.data.meteors
    
    def load_ngc(
        self,
        reload: bool = False,
        performance_trim: bool = False,
        magnitude_cutoff: Optional[float] = None
    ) -> pandas.DataFrame:
        """Load NGC catalog as a Pandas DataFrame.
        
        Args:
            reload: Force reload from JSON instead of cache
            performance_trim: Remove PGC entries for better performance
            magnitude_cutoff: Maximum magnitude to include (dimmer objects excluded)
            
        Returns:
            DataFrame with NGC objects
        """
        if self.data.ngc_df is None or reload:
            cache_exists = os.path.exists(self.paths.ngc_cache)
            
            if not reload and cache_exists:
                self._log("Loading NGC from cache", self.paths.ngc_cache, terminal=False)
                self.data.ngc_df = pandas.read_pickle(self.paths.ngc_cache)
            else:
                self._log("Generating NGC dataframe from", self.paths.ngc, terminal=True)
                self.data.ngc_df = self._generate_ngc_dataframe(
                    performance_trim=performance_trim
                )
                
            # Apply magnitude filter if specified
            if magnitude_cutoff is not None:
                self.data.ngc_df = self._trim_dim_ngc(
                    self.data.ngc_df, 
                    magnitude_cutoff
                )
                
        return self.data.ngc_df
    
    def _generate_ngc_dataframe(
        self,
        performance_trim: bool = False
    ) -> pandas.DataFrame:
        """Generate NGC DataFrame from JSON source.
        
        Args:
            performance_trim: Remove PGC entries for performance
            
        Returns:
            Processed NGC DataFrame
        """
        ngc_dict = self.load_json(self.paths.ngc)
        
        # Remove PGC entries for performance on 32-bit systems
        if performance_trim:
            deleted = 0
            for k in list(ngc_dict.keys()):
                if k.startswith('pgc'):
                    del ngc_dict[k]
                    deleted += 1
            self._log(f"Performance trim: removed {deleted} PGC entries", terminal=False)
        
        # Process each entry
        for name, values in ngc_dict.items():
            self._process_ngc_entry(name, values)
        
        # Convert to DataFrame
        df = pandas.DataFrame.from_dict(ngc_dict)
        df = df.transpose()
        
        # Save cache
        df.to_pickle(self.paths.ngc_cache)
        self._log("Saved NGC cache to", self.paths.ngc_cache, terminal=False)
        
        return df
    
    def _process_ngc_entry(self, name: str, entry: Dict) -> None:
        """Add computed fields to an NGC catalog entry."""
        # Right Ascension
        ra_h = entry.get('rah', 0)
        ra_m = entry.get('ram', 0)
        ra_s = entry.get('ras', 0)
        entry['radeg'] = self._hms_to_angle(ra_h, ra_m, ra_s)
        
        # Declination
        dec_d = entry.get('ded', 0)
        dec_m = entry.get('dem', 0)
        dec_s = entry.get('des', 0)
        entry['decdeg'] = self._dms_to_angle(dec_d, dec_m, dec_s)
        
        # Size (convert from arcseconds to degrees)
        width = float(entry.get('width', 0)) / 3600
        height = float(entry.get('height', 0)) / 3600
        if height == 0.0:
            height = width
        if width == 0.0:
            width = height
        if height == 0.0:
            height = width = 1 / 3600  # Default to 1 arcsecond
        entry['widthdeg'] = width
        entry['heightdeg'] = height
        
        # Name and type
        entry['name'] = name
        obj_type = entry.get('type', '').lower()
        entry['typelabel'] = self.NGC_TYPES.get(obj_type, obj_type)
        
        # Labels
        entry['ralabel'] = f"{ra_h}h {ra_m}m {ra_s}s"
        entry['declabel'] = f"{dec_d}d {dec_m}' {dec_s}\""
    
    def _trim_dim_ngc(
        self,
        df: pandas.DataFrame,
        cutoff: float
    ) -> pandas.DataFrame:
        """Remove NGC objects dimmer than cutoff magnitude."""
        before_count = len(df)
        df = df[df['magnitude'].between(-100, cutoff, inclusive='both')]
        self._log(
            f"NGC magnitude filter: {before_count} -> {len(df)} (cutoff {cutoff})",
            terminal=False
        )
        return df
    
    def load_comets(self, reload: bool = False) -> pandas.DataFrame:
        """Load comet orbital data from Minor Planet Center.
        
        Args:
            reload: Force reload from internet
            
        Returns:
            DataFrame indexed by comet designation
        """
        if self.data.comets_df is None or reload:
            from skyfield.data import mpc
            
            self._log('Loading comets from', mpc.COMET_URL, terminal=True)
            
            if self.skyfield_loader:
                with self.skyfield_loader.open(mpc.COMET_URL, reload=reload) as f:
                    comets = mpc.load_comets_dataframe(f)
            else:
                raise RuntimeError("Skyfield loader required for comet data")
            
            # Keep only most recent trajectory for each comet
            comets = (comets.sort_values('reference')
                     .groupby('designation', as_index=False).last()
                     .set_index('designation', drop=False))
            
            self.data.comets_df = comets
            self._log(f"Loaded {len(comets)} comets", terminal=False)
            
        return self.data.comets_df
    
    def get_comet_list(self) -> List[str]:
        """Get list of comet designations."""
        if self.data.comets_df is None:
            self.load_comets()
        return self.data.comets_df['designation'].tolist()
    
    def get_ngc_namelist(self) -> List[str]:
        """Get list of NGC object names."""
        if self.data.ngc_df is None:
            self.load_ngc()
        return self.data.ngc_df['name'].tolist()
    
    def load_constellations(self) -> Tuple[List[List[str]], Dict[str, str], List[str]]:
        """Load constellation patterns from Stellarium.
        
        Returns:
            Tuple of (links, names, star_list)
            - links: List of [star1_hip, star2_hip, constellation_name]
            - names: Dict mapping constellation codes to full names
            - star_list: List of HIP numbers in constellation patterns
        """
        if not self.data.constellation_links:
            from skyfield.api import load_constellation_names
            from skyfield.data import stellarium
            
            stellarium_url = 'https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/constellationship.fab'
            
            # Load constellation names
            for code, name in load_constellation_names():
                self.data.constellation_names[code.lower()] = name
            
            # Load constellation patterns
            if self.skyfield_loader:
                with self.skyfield_loader.open(stellarium_url) as f:
                    patterns = stellarium.parse_constellations(f)
            else:
                raise RuntimeError("Skyfield loader required for constellation data")
            
            # Process patterns into internal format
            for cons in patterns:
                code = cons[0]
                name = self.data.constellation_names.get(code.lower(), code)
                edges = cons[1]
                
                for star1, star2 in edges:
                    star1_str = str(star1)
                    star2_str = str(star2)
                    self.data.constellation_links.append([star1_str, star2_str, name])
                    
                    if star1_str not in self.data.constellation_stars:
                        self.data.constellation_stars.append(star1_str)
                    if star2_str not in self.data.constellation_stars:
                        self.data.constellation_stars.append(star2_str)
            
            self._log(
                f"Loaded {len(self.data.constellation_links)} constellation edges, "
                f"{len(self.data.constellation_stars)} stars",
                terminal=False
            )
            
        return (
            self.data.constellation_links,
            self.data.constellation_names,
            self.data.constellation_stars
        )
    
    def get_constellation_name(self, code: str) -> str:
        """Convert constellation code to full name."""
        if not self.data.constellation_names:
            self.load_constellations()
        return self.data.constellation_names.get(code.lower(), "")
    
    def load_planets(self, ephemeris: str = 'de421.bsp') -> Any:
        """Load planetary ephemeris data.
        
        Args:
            ephemeris: Ephemeris file to load (default: de421.bsp for inner planets)
            
        Returns:
            Skyfield ephemeris object
        """
        if self.data.planets is None:
            self._log("Loading planetary ephemeris", ephemeris, terminal=False)
            if self.skyfield_loader:
                self.data.planets = self.skyfield_loader(ephemeris)
            else:
                from skyfield.api import load as sf_load
                self.data.planets = sf_load(ephemeris)
        return self.data.planets
    
    def check_comet_data_age(self) -> Optional[int]:
        """Check how old the cached comet data is.
        
        Returns:
            Age in days, or None if no cached data
        """
        from datetime import datetime
        
        filename = os.path.join(self.paths.data_dir, 'CometEls.txt')
        if not os.path.exists(filename):
            return None
        
        try:
            with open(filename, 'r') as f:
                line = f.readline()
                # YYYYMMDD is at position 81:89 in MPC format
                date_str = line[81:89]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                age_days = (datetime.utcnow() - file_date).days
                
                if age_days > 60:
                    self._log(
                        f"Comet data is {age_days} days old. Consider refreshing.",
                        level='warning',
                        terminal=True
                    )
                return age_days
        except Exception:
            return None
    
    # Coordinate conversion utilities
    @staticmethod
    def _hms_to_angle(hours: float, minutes: float, seconds: float) -> float:
        """Convert hours/minutes/seconds to degrees."""
        total_hours = hours + minutes / 60 + seconds / 3600
        return total_hours * 15  # 15 degrees per hour
    
    @staticmethod
    def _dms_to_angle(degrees: float, minutes: float, seconds: float) -> float:
        """Convert degrees/minutes/seconds to decimal degrees."""
        sign = 1 if degrees >= 0 else -1
        return sign * (abs(degrees) + minutes / 60 + seconds / 3600)
    
    @staticmethod
    def _angle_to_hms(degrees: float) -> Tuple[int, int, float]:
        """Convert degrees to hours/minutes/seconds."""
        total_hours = degrees / 15
        hours = int(total_hours)
        minutes_float = (total_hours - hours) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        return hours, minutes, seconds
    
    @staticmethod
    def _angle_to_dms(degrees: float) -> Tuple[int, int, float]:
        """Convert decimal degrees to degrees/minutes/seconds."""
        sign = 1 if degrees >= 0 else -1
        degrees = abs(degrees)
        d = int(degrees)
        minutes_float = (degrees - d) * 60
        m = int(minutes_float)
        s = (minutes_float - m) * 60
        return sign * d, m, s


# Convenience functions for one-off loading
def load_dictionary(filename: str) -> Dict:
    """Load a JSON file as dictionary. Convenience wrapper."""
    return CatalogLoader.load_json(filename)


def hms_to_degrees(h: float, m: float, s: float) -> float:
    """Convert hours/minutes/seconds to degrees."""
    return CatalogLoader._hms_to_angle(h, m, s)


def dms_to_degrees(d: float, m: float, s: float) -> float:
    """Convert degrees/minutes/seconds to decimal degrees."""
    return CatalogLoader._dms_to_angle(d, m, s)


def degrees_to_hms(degrees: float) -> Tuple[int, int, float]:
    """Convert degrees to hours/minutes/seconds."""
    return CatalogLoader._angle_to_hms(degrees)


def degrees_to_dms(degrees: float) -> Tuple[int, int, float]:
    """Convert decimal degrees to degrees/minutes/seconds."""
    return CatalogLoader._angle_to_dms(degrees)
