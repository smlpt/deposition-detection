from dataclasses import dataclass
from typing import Dict, Optional
import csv
import logging

@dataclass
class ThresholdProfile:
    name: str
    h_decay: Optional[float] = None
    s_decay: Optional[float] = None
    v_decay: Optional[float] = None
    dh: Optional[float] = None
    ds: Optional[float] = None
    dv: Optional[float] = None
    ddh: Optional[float] = None
    dds: Optional[float] = None
    ddv: Optional[float] = None

class ProfileManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.profiles: Dict[str, ThresholdProfile] = {}
        
    def load_profiles(self, csv_path: str):
        """Load threshold profiles from CSV file"""
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert empty strings to None, otherwise convert to float
                    profile = ThresholdProfile(
                        name=row['name'],
                        **{key: float(val) if val.strip() else None 
                           for key, val in row.items() 
                           if key != 'name'}
                    )
                    self.profiles[profile.name] = profile
                    self.logger.debug(f"Loaded profile: {profile}")
            self.logger.info(f" Available threshold profiles: {', '.join(self.profiles.keys())}")
        except Exception as e:
            self.logger.error(f" Failed to load profiles: {str(e)}")
            
    def get_profile_names(self):
        """Get list of available profile names"""
        return list(self.profiles.keys())
    
    def get_profile(self, name: str) -> ThresholdProfile:
        """Get profile by name"""
        return self.profiles.get(name)