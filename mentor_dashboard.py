import os

import klembord
from bs4 import BeautifulSoup

import gdrive
import shell_integration
import threading

def getHTMLFromClipboard():
    return klembord.get(['text/html'])['text/html']

def extractLinks(cell_node):
    links = {}
    link_nodes = cell_node.find_all("a")
    for link_node in link_nodes:
        links[link_node.get_text()] = link_node.get("href")
    return links

class Project(object):

    column_names = ["unit", "name", "date", "work", "rubric", "solution", "grade"]
    column_parsers = {
        "name": extractLinks,
        "work": extractLinks,
        "rubric": extractLinks,
        "solution": extractLinks
    }

    def __init__(self, row_node,
                 startCallback=None, progressCallback=None, completionCallback=None):
        cells = row_node.find_all("td", recursve=False)
        if len(cells) != len(Project.column_names):
            raise Exception()
        for idx, cell in enumerate(cells):
            col_name = Project.column_names[idx]
            if col_name in Project.column_parsers:
                col_value = Project.column_parsers[col_name](cell)
            else:
                col_value = cell.get_text()
            setattr(self, col_name, col_value)
        self.projectLinks = self.name
        self.name = " ".join(self.projectLinks.keys())
        self.openContexts = []
        self.startCallback = startCallback
        self.progressCallback = progressCallback
        self.completionCallback = completionCallback

    def getLocalURIs(self):
        local_uris = {}
        # TODO: parameterize
        download_dir = os.path.join(os.getcwd(), "downloads")
        project_dir = os.path.join(download_dir, "%s %s" % (
            self.unit, shell_integration.sanitizeFilesystemName(self.name)))
        for link_name, link in self.work.items():
            link_dir = os.path.join(project_dir, shell_integration.sanitizeFilesystemName(link_name))
            if os.path.exists(link_dir):
                local_uris[link_name] = link_dir
            else:
                if self.startCallback is not None:
                    self.startCallback()
                result = gdrive.downloadGoogleURL(
                    link, cwd=download_dir, dirname=link_dir,
                    progressCallback=self.progressCallback)
                if self.completionCallback is not None:
                    self.completionCallback()
                if result is not None:
                    shell_integration.expandArchives(result["local_uri"])
                    local_uris[link_name] = result["local_uri"]
        return local_uris

    def close(self):
        for context in self.openContexts:
            context()
        self.openContexts.clear()

    def open(self, openCompletionCallback=None):
        def body():
            local_uris = self.getLocalURIs()
            for uri in local_uris.values():
                self.openContexts.extend(shell_integration.openAllFiles(uri))
            if openCompletionCallback is not None:
                openCompletionCallback()
        threading.Thread(target=body).start()


def getProjectsFromHTML(html):
    projects = []
    parsed_result = BeautifulSoup(html, 'html.parser')
    rows = parsed_result.find_all("tr")
    for row in rows:
        try:
            project = Project(row)
            projects.append(project)
        except Exception:
            pass
    return projects
