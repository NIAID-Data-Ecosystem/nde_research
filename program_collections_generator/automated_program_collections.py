#!/usr/bin/env python3
"""
Automated Program Collections Generator

This script automates the association of funding IDs and program collections.
It can be triggered automatically when new builds are created in DEV or
Staging.

Features:
- Downloads the latest program metadata from Google Sheets
- Handles programs with transferred control
- Generates both staging and production correction files
- Supports webhook triggers and scheduled runs
- Includes error handling and logging

Usage:
    python automated_program_collections.py [--environment staging|production]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('program_collections.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ProgramCollectionsAutomator:
    """Main class for automating program collections generation"""

    def __init__(self, base_path: str = None):
        """Initialize the automator with configuration"""
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.data_path = self.base_path / 'data'
        self.script_path = self.base_path

        # Configuration
        self.google_sheets_url = "https://docs.google.com/spreadsheets/d/16ioasEqMoXuv2tgJs7xlMgD_sPLvrxs7Cp3rwz273YE/export?format=xlsx&gid=0"
        self.staging_api_url = "https://api-staging.data.niaid.nih.gov/v1/query"
        self.production_api_url = "https://api.data.niaid.nih.gov/v1/query"

        # GitHub raw URLs for control files (fallback)
        self.control_transferred_url = "https://raw.githubusercontent.com/NIAID-Data-Ecosystem/nde_research/main/program_collections_generator/data/control_transferred.txt"
        self.approved_prod_url = "https://raw.githubusercontent.com/NIAID-Data-Ecosystem/nde_research/main/program_collections_generator/data/approved_for_prod.txt"

        # Find correction path
        self.correction_path = self._find_correction_path()

        # Load configuration data
        self.approved_prod = []
        self.control_transferred = []
        self.act_codes = []
        self.ic_codes = []

    def _find_correction_path(self) -> Path:
        """Find the nde-metadata-corrections path"""
        # Try common locations
        possible_paths = [
            self.base_path.parent.parent / 'nde-metadata-corrections',
            self.base_path.parent / 'nde-metadata-corrections',
            Path.home() / 'nde-metadata-corrections',
            Path('/tmp/nde-metadata-corrections')  # Fallback for CI/CD
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"Found correction path: {path}")
                return path

        # If not found, create a temporary directory
        temp_path = Path('/tmp/nde-metadata-corrections')
        temp_path.mkdir(exist_ok=True)
        (temp_path / 'collections_corrections_staging').mkdir(exist_ok=True)
        (temp_path / 'collections_corrections_production').mkdir(exist_ok=True)
        logger.warning(f"Created temporary correction path: {temp_path}")
        return temp_path

    def load_configuration(self) -> bool:
        """Load all configuration files and data"""
        try:
            # Load approved production programs
            self.approved_prod = self._load_list_file(
                self.data_path / 'approved_for_prod.txt',
                self.approved_prod_url
            )

            # Load control transferred programs
            self.control_transferred = self._load_list_file(
                self.data_path / 'control_transferred.txt',
                self.control_transferred_url
            )

            # Load NIH codes
            self.act_codes, self.ic_codes = self._load_nih_codes()

            logger.info(
                f"Loaded {len(self.approved_prod)} approved production programs")
            logger.info(
                f"Loaded {len(self.control_transferred)} control transferred programs")
            logger.info(
                f"Loaded {len(self.act_codes)} activity codes and {len(self.ic_codes)} IC codes")

            return True

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False

    def _load_list_file(self, local_path: Path, remote_url: str) -> List[str]:
        """Load a list file from local path or remote URL"""
        items = []

        # Try local file first
        if local_path.exists():
            try:
                with open(local_path, 'r') as f:
                    items = [line.strip() for line in f if line.strip()]
                logger.info(f"Loaded {len(items)} items from {local_path}")
                return items
            except Exception as e:
                logger.warning(f"Failed to read local file {local_path}: {e}")

        # Fallback to remote URL
        try:
            response = requests.get(remote_url, timeout=30)
            response.raise_for_status()
            items = [line.strip()
                     for line in response.text.split('\n') if line.strip()]
            logger.info(f"Loaded {len(items)} items from {remote_url}")
        except Exception as e:
            logger.error(f"Failed to fetch from {remote_url}: {e}")

        return items

    def _load_nih_codes(self) -> Tuple[List[str], List[str]]:
        """Load NIH activity and IC codes"""
        act_codes = []
        ic_codes = []

        try:
            # Load activity codes
            act_codes_path = self.data_path / 'NIH_activity_codes.csv'
            if act_codes_path.exists():
                df = pd.read_csv(act_codes_path)
                act_codes = df['Activity Code'].unique().tolist()
                act_codes = [x.strip() for x in act_codes if pd.notna(x)]

            # Load IC codes
            ic_codes_path = self.data_path / 'NIH_IC_codes.tsv'
            if ic_codes_path.exists():
                df = pd.read_csv(ic_codes_path, delimiter='\t')
                ic_codes = df['Code'].unique().tolist()
                ic_codes = [x.strip() for x in ic_codes if pd.notna(x)]

        except Exception as e:
            logger.error(f"Failed to load NIH codes: {e}")

        return act_codes, ic_codes

    def download_program_metadata(self) -> pd.DataFrame:
        """Download the latest program metadata from Google Sheets"""
        try:
            logger.info("Downloading program metadata from Google Sheets...")

            # Download the Excel file
            response = requests.get(self.google_sheets_url, timeout=60)
            response.raise_for_status()

            # Save temporarily and read with pandas
            temp_file = self.data_path / 'temp_program_collections.xlsx'
            with open(temp_file, 'wb') as f:
                f.write(response.content)

            # Read the metadata sheet
            df = pd.read_excel(
                temp_file, sheet_name='metadata', engine='openpyxl')

            # Clean up temporary file
            temp_file.unlink()

            logger.info(f"Downloaded program metadata: {df.shape[0]} programs")
            return df

        except Exception as e:
            logger.error(f"Failed to download program metadata: {e}")
            # Fallback to local file if it exists
            local_file = self.data_path / 'Program Collections.xlsx'
            if local_file.exists():
                logger.warning(
                    "Using local Program Collections.xlsx as fallback")
                return pd.read_excel(local_file, sheet_name='metadata', engine='openpyxl')
            else:
                raise Exception("No program metadata available")

    def parse_array_text(self, array_text: str) -> List[str]:
        """Parse comma or pipe-separated text into a list"""
        if pd.isna(array_text) or array_text == 'not found':
            return []

        # Remove asterisks
        array_text = str(array_text).replace('*', '')

        # Split by comma or pipe
        if ',' in array_text:
            items = array_text.split(',')
        elif '|' in array_text:
            items = array_text.split('|')
        else:
            items = [array_text]

        return [x.strip() for x in items if x.strip()]

    def parse_grant_id(self, grant_id: str) -> Dict[str, str]:
        """Parse a grant ID into its components"""
        grant_id = grant_id.strip()

        # Initialize result
        result = {
            'grantID': grant_id,
            'applTypeCode': 'not found',
            'activityCode': 'not found',
            'icCode': 'not found',
            'serialNum': 'not found',
            'supportYear': 'not found'
        }

        try:
            # Check for support year at the end
            if '-' in grant_id[-5:]:
                result['supportYear'] = grant_id[-2:]

            # Determine starting pattern
            if grant_id[0].isdigit():
                if grant_id[:2].isdigit():
                    # Contract ID
                    return result
                else:
                    # Application type code
                    result['applTypeCode'] = grant_id[0]
                    remaining = grant_id[2:] if grant_id[1] in '-_ ' else grant_id[1:]
            else:
                remaining = grant_id

            # Parse activity code
            for code in self.act_codes:
                if remaining.startswith(code):
                    result['activityCode'] = code
                    remaining = remaining[len(code):]
                    if remaining.startswith('-'):
                        remaining = remaining[1:]
                    break

            # Parse IC code
            for code in self.ic_codes:
                if remaining.startswith(code):
                    result['icCode'] = code
                    remaining = remaining[len(code):]
                    if remaining.startswith('-'):
                        remaining = remaining[1:]
                    break

            # Parse serial number (first 6 digits typically)
            serial_match = ''
            for char in remaining:
                if char.isdigit():
                    serial_match += char
                    if len(serial_match) >= 6:
                        break
                elif char == '-':
                    break

            if serial_match:
                result['serialNum'] = serial_match

        except Exception as e:
            logger.warning(f"Failed to parse grant ID {grant_id}: {e}")

        return result

    def parse_program_funding(self, funding_info: str) -> List[str]:
        """Parse program funding information into standardized grant IDs"""
        if pd.isna(funding_info) or funding_info == 'not found':
            return []

        grant_list = []
        grants = self.parse_array_text(funding_info)

        for grant in grants:
            grant = grant.replace("*", "").strip()
            try:
                parsed = self.parse_grant_id(grant)
                if parsed['icCode'] != 'not found' and parsed['serialNum'] != 'not found':
                    # Use IC code + serial number for better matching
                    grant_list.append(parsed['icCode'] + parsed['serialNum'])
                else:
                    grant_list.append(grant)
            except:
                grant_list.append(grant)

        return grant_list

    def search_for_records(self, grant_list: List[str], environment: str = 'staging') -> pd.DataFrame:
        """Search for records matching the grant IDs"""
        api_url = self.staging_api_url if environment == 'staging' else self.production_api_url
        result_list = []
        fail_list = []

        for grant in grant_list:
            try:
                # Try both wildcard and exact searches
                wildcard_url = f"{api_url}?&q=funding.identifier:*{grant}*&fields=_id,funding.identifier&size=500"
                exact_url = f"{api_url}?&q=funding.identifier:{grant}&fields=_id,funding.identifier&size=500"

                responses = []
                for url in [wildcard_url, exact_url]:
                    try:
                        response = requests.get(url, timeout=30)
                        response.raise_for_status()
                        data = response.json()
                        if 'hits' in data and len(data['hits']) > 0:
                            responses.extend(data['hits'])
                    except Exception as e:
                        logger.warning(
                            f"Search failed for {grant} at {url}: {e}")

                if responses:
                    for hit in responses:
                        record_id = hit['_id']
                        funding_data = hit.get('funding', [])

                        if isinstance(funding_data, list):
                            for funding in funding_data:
                                if grant in funding.get('identifier', ''):
                                    result_list.append({
                                        'query': grant,
                                        '_id': record_id,
                                        'fundID': funding['identifier']
                                    })
                        elif isinstance(funding_data, dict):
                            if grant in funding_data.get('identifier', ''):
                                result_list.append({
                                    'query': grant,
                                    '_id': record_id,
                                    'fundID': funding_data['identifier']
                                })
                else:
                    fail_list.append(grant)

            except Exception as e:
                logger.error(f"Error searching for grant {grant}: {e}")
                fail_list.append(grant)

        if fail_list:
            logger.warning(f"Failed to find records for grants: {fail_list}")

        if result_list:
            df = pd.DataFrame(result_list)
            return df.drop_duplicates(subset=['_id'], keep='first')
        else:
            return pd.DataFrame(columns=['query', '_id', 'fundID'])

    def get_prior_records(self, filename: str, environment: str) -> List[str]:
        """Get prior records for programs with transferred control"""
        try:
            if environment == 'production':
                url = f"https://raw.githubusercontent.com/NIAID-Data-Ecosystem/nde-metadata-corrections/refs/heads/main/collections_corrections_production/{filename}_records.txt"
            else:
                url = f"https://raw.githubusercontent.com/NIAID-Data-Ecosystem/nde-metadata-corrections/refs/heads/main/collections_corrections_staging/{filename}_records.txt"

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            prior_records = []
            for line in response.text.split('\n'):
                line = line.strip()
                if line and line.startswith('https://data.niaid.nih.gov/resources?id='):
                    record_id = line.replace(
                        'https://data.niaid.nih.gov/resources?id=', '')
                    prior_records.append(record_id)

            logger.info(
                f"Found {len(prior_records)} prior records for {filename}")
            return prior_records

        except Exception as e:
            logger.warning(
                f"Could not fetch prior records for {filename}: {e}")
            return []

    def generate_correction_files(self, df: pd.DataFrame, environment: str = 'both') -> Dict[str, int]:
        """Generate correction files for all programs"""
        stats = {'metadata_files': 0, 'record_files': 0, 'errors': 0}

        # Filter valid programs
        valid_programs = df[
            (~df['fundingIDList'].isna()) &
            (df['fundingIDList'] != 'not found') &
            (~df['niaidURL'].isna()) &
            (df['fileName'] != '--')
        ].copy()

        logger.info(f"Processing {len(valid_programs)} valid programs")

        for _, row in valid_programs.iterrows():
            try:
                filename = row['fileName']

                # Skip if in do-not-update list and not approved for production
                if filename in self.control_transferred and filename not in self.approved_prod:
                    logger.info(
                        f"Skipping {filename} - control transferred but not approved for production")
                    continue

                # Determine target environment
                if filename in self.approved_prod:
                    target_env = 'production'
                else:
                    target_env = 'staging'

                # Skip if environment filter doesn't match
                if environment != 'both' and environment != target_env:
                    continue

                # Generate metadata file
                self._generate_metadata_file(row, target_env)
                stats['metadata_files'] += 1

                # Generate records file
                self._generate_records_file(row, target_env)
                stats['record_files'] += 1

            except Exception as e:
                logger.error(
                    f"Error processing program {row.get('fileName', 'unknown')}: {e}")
                stats['errors'] += 1

        return stats

    def _generate_metadata_file(self, row: pd.Series, environment: str):
        """Generate metadata correction file for a program"""
        filename = row['fileName']

        # Parse alternate names and parent organizations
        alt_names = self.parse_array_text(row.get('alternateName', ''))
        parent_orgs = self.parse_array_text(row.get('parentOrganization', ''))

        # Create metadata object
        description = f"{row['description']} For more information, visit the NIAID program page: {row['niaidURL']}"

        metadata = {
            "@type": "ResearchProject",
            "name": row["name"],
            "abstract": row["abstract"],
            "description": description,
            "alternateName": alt_names,
            "url": row["url"],
            "parentOrganization": parent_orgs
        }

        output_data = {"sourceOrganization": [metadata]}

        # Determine output path
        if environment == 'production':
            output_dir = self.correction_path / 'collections_corrections_production'
        else:
            output_dir = self.correction_path / 'collections_corrections_staging'

        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f'{filename}_correction.json'

        # Write file
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=4)

        logger.info(f"Generated metadata file: {output_file}")

    def _generate_records_file(self, row: pd.Series, environment: str):
        """Generate records file for a program"""
        filename = row['fileName']

        # Parse funding information
        base_grants = self.parse_program_funding(row['fundingIDList'])
        prior_grants = self.parse_array_text(
            row.get('PriorProjectGrantIDs', ''))

        # Combine grant lists
        all_grants = list(set(base_grants + prior_grants))

        if not all_grants:
            logger.warning(f"No grants found for {filename}")
            return

        # Search for records
        search_env = environment if environment == 'production' else 'staging'
        search_results = self.search_for_records(all_grants, search_env)

        # Get unique record IDs
        if not search_results.empty:
            record_ids = search_results['_id'].unique().tolist()
        else:
            record_ids = []

        # For control transferred programs, merge with prior records
        if filename in self.control_transferred:
            prior_records = self.get_prior_records(filename, environment)
            record_ids = list(set(record_ids + prior_records))

        # Determine output path
        if environment == 'production':
            output_dir = self.correction_path / 'collections_corrections_production'
        else:
            output_dir = self.correction_path / 'collections_corrections_staging'

        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f'{filename}_records.txt'

        # Write records file
        with open(output_file, 'w') as f:
            for record_id in sorted(record_ids):
                # Handle immport prefix
                if "immport" in record_id:
                    clean_id = record_id.replace("immport_", "")
                    f.write(
                        f'https://data.niaid.nih.gov/resources?id={clean_id}\n')
                else:
                    f.write(
                        f'https://data.niaid.nih.gov/resources?id={record_id}\n')

        logger.info(
            f"Generated records file: {output_file} ({len(record_ids)} records)")

    def run_automation(self, environment: str = 'both', force_update: bool = False) -> bool:
        """Run the complete automation process"""
        try:
            logger.info(
                f"Starting program collections automation (environment: {environment})")

            # Load configuration
            if not self.load_configuration():
                return False

            # Download latest program metadata
            df = self.download_program_metadata()

            # Generate correction files
            stats = self.generate_correction_files(df, environment)

            logger.info(f"Automation completed successfully!")
            logger.info(f"Generated {stats['metadata_files']} metadata files")
            logger.info(f"Generated {stats['record_files']} record files")

            if stats['errors'] > 0:
                logger.warning(
                    f"Encountered {stats['errors']} errors during processing")

            return True

        except Exception as e:
            logger.error(f"Automation failed: {e}")
            return False


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Automate program collections generation')
    parser.add_argument('--environment', choices=['staging', 'production', 'both'],
                        default='both', help='Target environment')
    parser.add_argument('--force-update', action='store_true',
                        help='Force update even if no changes detected')
    parser.add_argument('--base-path', help='Base path for the script')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default='INFO', help='Logging level')

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Initialize automator
    automator = ProgramCollectionsAutomator(args.base_path)

    # Run automation
    success = automator.run_automation(args.environment, args.force_update)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
