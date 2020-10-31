import os
import mimetypes
import pickle
import re
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient.http import MediaIoBaseDownload

import shell_integration

SRC_DIR = os.path.dirname(os.path.realpath(__file__))

class GdriveClient(object):
    CREDENTIALS_FILE = os.path.join(SRC_DIR, 'credentials', 'gdrive_springboard_credentials.json')
    TOKEN_FILE = os.path.join(SRC_DIR, 'credentials', 'gdrive_springboard_token.pickle')
    SCOPES = ('https://www.googleapis.com/auth/drive.readonly',)

    GDRIVE_URL_PARSER = re.compile(r"(?:https?://)?"
                                   r"(?:[^.]*).google.com/(?:drive/)?"
                                   r"([A-Za-z]*)/(?:d/)?([^/?]+)")

    def __init__(self, token_file=TOKEN_FILE, credentials_file=CREDENTIALS_FILE):
        self.token_file = token_file
        self.credentials_file = credentials_file
        self.creds = None
        self.service = None

    def initialized(self):
        return self.service is not None

    def initialize(self, attemptAuthorization=True):
        # TODO: cursify using https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html
        self.creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                self.creds = pickle.load(token)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if attemptAuthorization is False:
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(self.token_file, 'wb') as token:
                pickle.dump(self.creds, token)
        self.service = build('drive', 'v3', credentials=self.creds)
        return True

    def downloadGDriveFile(self, file_id, local_path, exportMIMEType=None, metadata=None, progressCallback=None):
        if self.service is None:
            raise Exception("GDrive service not initialized")

        if metadata is None:
            metadata = self.service.files().get(fileId=file_id).execute()
        filename = os.path.join(local_path, metadata["name"])
        if exportMIMEType is None:
            content_request = self.service.files().get_media(fileId=file_id)
        else:
            content_request = self.service.files().export_media(fileId=file_id, mimeType=exportMIMEType)
            filename += mimetypes.guess_extension(exportMIMEType)
        with open(os.path.join(local_path, filename), "wb") as f:
            downloader = MediaIoBaseDownload(f, content_request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if progressCallback is not None:
                    progressCallback(metadata, status.progress())
        metadata["local_uri"] = filename
        return metadata

    def getGDriveTree(self, dir_id):
        if self.service is None:
            raise Exception("GDrive service not initialized")

        page_token = None
        directory = {"files": [], "dirs": {}}

        response_files = []
        while True:
            response = self.service.files().list(
                q="'%s' in parents" % dir_id,
                spaces='drive',
                pageSize=100,
                fields='nextPageToken, files(name, mimeType, id)',
                pageToken=page_token
            ).execute()
            page_token = response.get('nextPageToken', None)
            response_files.extend(response.get('files', []))
            if page_token is None:
                break

        for file in response_files:
            if file["mimeType"].endswith("folder"):
                file["contents"] = self.getGDriveTree(file["id"])
                directory["dirs"][file["id"]] = file
            else:
                directory["files"].append(file)
        return directory

    def downloadGdriveFolder(self, dir_id, cwd, progressCallback=None):
        if self.service is None:
            raise Exception("GDrive service not initialized")

        directory_tree = self.getGDriveTree(dir_id)

        def dir_helper(dir_contents, local_path):
            for file in dir_contents["files"]:
                self.downloadGDriveFile(
                    file["id"],
                    metadata=file,
                    local_path=local_path,
                    progressCallback=progressCallback)
            for directory in dir_contents["dirs"].values():
                subdir_path = os.path.join(local_path, directory["name"])
                directory["local_uri"] = subdir_path
                os.makedirs(subdir_path, exist_ok=True)
                dir_helper(directory["contents"], subdir_path)
        dir_helper(directory_tree, cwd)
        directory_tree["local_uri"] = cwd
        return directory_tree

    def downloadURL(self, url, cwd=os.getcwd(), dirname=None, progressCallback=None):
        if self.service is None:
            raise Exception("GDrive service not initialized")
        result = None
        match = self.GDRIVE_URL_PARSER.match(url)
        if match is not None:
            link_type = match.group(1)
            gdrive_id = match.group(2)

            if dirname is None:
                dirname = gdrive_id
            base_dir = os.path.join(cwd, dirname)
            os.makedirs(base_dir, exist_ok=True)
            shell_integration.makeURLShortcut(url, base_dir, "Drive Link", "Link to original file source")

            if link_type == "file":
                result = {"local_uri": base_dir, "dirs": {}, "files": [
                    self.downloadGDriveFile(
                        gdrive_id, base_dir,
                        progressCallback=progressCallback)
                ]}
            elif link_type == "folders":
                result = self.downloadGdriveFolder(
                    gdrive_id, base_dir,
                    progressCallback=progressCallback)
            elif link_type == "document":
                result = {"local_uri": base_dir, "dirs": {}, "files": [
                    self.downloadGDriveFile(
                        gdrive_id, base_dir,
                        exportMIMEType='application/pdf',
                        progressCallback=progressCallback)
                ]}
            else:
                raise ValueError("Invalid Google Drive URL '%s'" % url)
        return result

