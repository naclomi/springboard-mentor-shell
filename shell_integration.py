import klembord
import os
import shutil
import subprocess
import mimetypes


class SublimeIDE(object):
    @staticmethod
    def open(fs_root, files):
        subprocess.run(["subl", "-n", fs_root] + files,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return SublimeIDE.close

    @staticmethod
    def close():
        # TODO
        pass


class GnomeGeneric(object):
    @staticmethod
    def open(fs_root, files):
        subprocess.run(["xdg-open"] + files,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return GnomeGeneric.close

    @staticmethod
    def close():
        # TODO
        pass


def sanitizeFilesystemName(string):
    return "".join([c for c in string if c.isalpha() or c.isdigit() or c==' ']).rstrip()


def makeURLShortcut(url, cwd, name, desc):
    name = sanitizeFilesystemName(name)
    full_dir = os.path.join(cwd, name + ".desktop")
    with open(full_dir, "w") as f:
        f.write("""
[Desktop Entry]
Encoding=UTF-8
Name={desc}
Type=Link
URL={url}
Icon=text-html
""".format(**locals()))
    return full_dir


def expandArchives(fs_root):
    archive_extensions = []
    for _, file_types, _ in shutil.get_unpack_formats():
        archive_extensions.extend(file_types)
    for root, dirs, files in os.walk(fs_root):
        for file in files:
            name, ext = os.path.splitext(file)
            if ext in archive_extensions:
                archive_file = os.path.join(root, file)
                extract_dir = os.path.join(root, name + ".extracted")
                os.makedirs(extract_dir, exist_ok=True)
                shutil.unpack_archive(archive_file, extract_dir=extract_dir)
                dirs.append(extract_dir)


def openAllFiles(fs_root):
    file_lists = {
        "plaintext": [],
        "pdf": []
    }

    for root, _, files in os.walk(fs_root):
        for filename in files:
            try:
                mimetype = mimetypes.guess_type(filename)[0]
                major, minor = mimetype.split("/")
                file_list = None
                if major == "text" or minor in ("javascript", "json", "xml", "x-sql"):
                    file_list = "plaintext"
                elif mimetype == "application/pdf":
                    file_list = "pdf"
                if file_list is not None:
                    full_path = os.path.join(root, filename)
                    file_lists[file_list].append(full_path)
            except Exception:
                pass

    openContexts = []
    if len(file_lists["plaintext"]) > 0:
        openContexts.append(SublimeIDE.open(fs_root, file_lists["plaintext"]))
    if len(file_lists["pdf"]) > 0:
        openContexts.append(GnomeGeneric.open(fs_root, file_lists["pdf"]))
    return openContexts


def openLink(url):
    if not url.startswith("http"):
        url = "http://" + url
    GnomeGeneric.open(None, [url])


def syncShells(new_path):
    with open("/tmp/springboard_active_directory", "w") as f:
        f.write(new_path)


def openFolder(uri):
    GnomeGeneric.open(None, [uri])


def copyText(text):
    klembord.set_text(text)


def getHTMLFromClipboard():
    return klembord.get(['text/html'])['text/html']
