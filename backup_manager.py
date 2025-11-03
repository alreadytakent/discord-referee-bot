import os
import pickle
import io
import json
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import sqlite3


class BackupManager:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file']
        self.service = None
        self.backup_folder_id = None
        self.initialize_service()

    def initialize_service(self):
        """Initialize Google Drive service with OAuth"""
        creds = None

        # Check if we have token saved
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # You'll need to create credentials.json from Google Cloud Console
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        self.service = build('drive', 'v3', credentials=creds)
        self.setup_backup_folder()

    def setup_backup_folder(self):
        """Create or find the backup folder"""
        folder_name = 'DiscordBotBackups'

        # Check if folder exists
        response = self.service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
            spaces='drive'
        ).execute()

        if not response['files']:
            # Create folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            self.backup_folder_id = folder['id']
        else:
            self.backup_folder_id = response['files'][0]['id']

    def backup_database(self, db_path, backup_name):
        """Backup a single database file"""
        if not os.path.exists(db_path):
            print(f"Database file {db_path} not found")
            return False

        try:
            # Read database file
            with open(db_path, 'rb') as f:
                file_data = f.read()

            # Create file metadata
            file_metadata = {
                'name': f'{backup_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db',
                'parents': [self.backup_folder_id]
            }

            # Create media object
            media = MediaIoBaseUpload(io.BytesIO(file_data),
                                      mimetype='application/x-sqlite3',
                                      resumable=True)

            # Upload file
            file = self.service.files().create(body=file_metadata,
                                               media_body=media,
                                               fields='id').execute()

            print(f"Backed up {db_path} as {file_metadata['name']}")
            return True

        except Exception as e:
            print(f"Error backing up {db_path}: {e}")
            return False

    def restore_database(self, db_path, backup_name=None):
        """Restore database from latest backup"""
        try:
            # Find the latest backup file
            query = f"'{self.backup_folder_id}' in parents and name contains '{backup_name}'"
            if backup_name:
                query += f" and name contains '{backup_name}'"

            response = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, createdTime)',
                orderBy='createdTime desc'
            ).execute()

            if not response['files']:
                print(f"No backup found for {backup_name}")
                return False

            # Get the latest backup
            latest_backup = response['files'][0]
            print(f"Restoring from backup: {latest_backup['name']}")

            # Download the file
            request = self.service.files().get_media(fileId=latest_backup['id'])
            file_data = io.BytesIO()
            downloader = MediaIoBaseDownload(file_data, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%")

            # Write to local file
            with open(db_path, 'wb') as f:
                f.write(file_data.getvalue())

            print(f"Restored {db_path} from backup")
            return True

        except Exception as e:
            print(f"Error restoring {db_path}: {e}")
            return False

    def backup_all_databases(self):
        """Backup all database files"""
        print("Starting database backup...")

        databases = [
            ('game_results.db', 'gameresults'),
            ('kod_results.db', 'kodresults')
        ]

        success_count = 0
        for db_file, backup_name in databases:
            if os.path.exists(db_file):
                if self.backup_database(db_file, backup_name):
                    success_count += 1

        print(f"Backup completed: {success_count}/{len(databases)} databases backed up")
        return success_count

    def restore_all_databases(self):
        """Restore all database files"""
        print("Starting database restore...")

        databases = [
            ('game_results.db', 'gameresults'),
            ('kod_results.db', 'kodresults')
        ]

        success_count = 0
        for db_file, backup_name in databases:
            if self.restore_database(db_file, backup_name):
                success_count += 1

        print(f"Restore completed: {success_count}/{len(databases)} databases restored")
        return success_count

    def cleanup_old_backups(self, days_to_keep=30):
        """Delete backups older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            response = self.service.files().list(
                q=f"'{self.backup_folder_id}' in parents",
                spaces='drive',
                fields='files(id, name, createdTime)'
            ).execute()

            deleted_count = 0
            for file in response['files']:
                file_date = datetime.strptime(file['createdTime'], '%Y-%m-%dT%H:%M:%S.%fZ')
                if file_date < cutoff_date:
                    self.service.files().delete(fileId=file['id']).execute()
                    deleted_count += 1
                    print(f"Deleted old backup: {file['name']}")

            print(f"Cleanup completed: {deleted_count} old backups deleted")

        except Exception as e:
            print(f"Error during cleanup: {e}")


# Global backup manager instance
backup_manager = None


def get_backup_manager():
    global backup_manager
    if backup_manager is None:
        backup_manager = BackupManager()
    return backup_manager


def initialize_backup_system():
    """Initialize backup system on bot startup"""
    if os.getenv('RENDER'):
        print("Running on Render - initializing backup system...")
        manager = get_backup_manager()

        # Try to restore databases on startup
        restored = manager.restore_all_databases()

        if restored > 0:
            print("Databases restored from backup")
        else:
            print("No backups found or restore failed - starting with fresh databases")

        return manager
    return None