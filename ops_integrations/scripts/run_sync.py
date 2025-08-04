#!/usr/bin/env python3
"""
Plumbing AGI ETL Sync Script
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from ops_integrations.etl.ops_etl import OpsETLSync

if __name__ == "__main__":
    OpsETLSync().run()