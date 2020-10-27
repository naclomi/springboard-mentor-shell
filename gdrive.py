import os
import mimetypes
import pickle
import re
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient.http import MediaIoBaseDownload

import shell_integration

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

# TODO: handle other working directories
SRC_DIR = os.path.dirname(os.path.realpath(__file__))
CREDENTIALS_FILE = os.path.join(SRC_DIR, 'gdrive_springboard_credentials.json')
TOKEN_FILE = os.path.join(SRC_DIR, 'gdrive_springboard_token.pickle')

DEFAULT_GDRIVE_CLIENT = None

# TODO: Curses-ify
def initGDrive(token_file=TOKEN_FILE, credentials_file=CREDENTIALS_FILE):
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service


def defaultClient():
    global DEFAULT_GDRIVE_CLIENT
    if DEFAULT_GDRIVE_CLIENT is None:
        DEFAULT_GDRIVE_CLIENT = initGDrive()
    return DEFAULT_GDRIVE_CLIENT


def downloadGDriveFile(drive_service, file_id, local_path, exportMIMEType=None, metadata=None, progressCallback=None):
    if metadata is None:
        metadata = drive_service.files().get(fileId=file_id).execute()
    filename = os.path.join(local_path, metadata["name"])
    if exportMIMEType is None:
        content_request = drive_service.files().get_media(fileId=file_id)
    else:
        content_request = drive_service.files().export_media(fileId=file_id, mimeType=exportMIMEType)
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


def getGDriveTree(drive_service, dir_id):
    page_token = None
    directory = {"files": [], "dirs": {}}

    response_files = []
    while True:
        response = drive_service.files().list(
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
            file["contents"] = getGDriveTree(drive_service, file["id"])
            directory["dirs"][file["id"]] = file
        else:
            directory["files"].append(file)
    return directory


def downloadGdriveFolder(drive_service, dir_id, cwd, progressCallback=None):
    directory_tree = getGDriveTree(drive_service, dir_id)

    def dir_helper(dir_contents, local_path):
        for file in dir_contents["files"]:
            downloadGDriveFile(
                drive_service,
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


GDRIVE_URL_PARSER = re.compile(r"(?:https?://)?"
                               r"(?:[^.]*).google.com/(?:drive/)?"
                               r"([A-Za-z]*)/(?:d/)?([^/?]+)")

def downloadGoogleURL(url, cwd=os.getcwd(), dirname=None, progressCallback=None, drive_service=None):
    if drive_service is None:
        drive_service = defaultClient()

    result = None
    match = GDRIVE_URL_PARSER.match(url)
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
                downloadGDriveFile(drive_service,
                    gdrive_id, base_dir,
                    progressCallback=progressCallback)
            ]}
        elif link_type == "folders":
            result = downloadGdriveFolder(
                drive_service,
                gdrive_id, base_dir,
                progressCallback=progressCallback)
        elif link_type == "document":
            result = {"local_uri": base_dir, "dirs": {}, "files": [
                downloadGDriveFile(drive_service,
                    gdrive_id, base_dir,
                    exportMIMEType='application/pdf',
                    progressCallback=progressCallback)
            ]}
        else:
            raise ValueError("Invalid Google Drive URL '%s'" % url)
    return result

