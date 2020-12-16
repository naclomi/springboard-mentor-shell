import os
import re
import git

# https://github.com/(user)/(repo)/tree/(branch)
#
# git@github.com:(user)/(repo).git
# git checkout (branch)
class GithubClient(object):
    GITHUB_URL_PARSER = re.compile(r"(?:https?://)?"
                               r"(?:[^.]*).github.com/(.*)")

    def __init__(self):
        pass

    def matchURL(self, url):
        return self.GITHUB_URL_PARSER.match(url) is not None

    def initialized(self):
        return True

    def initialize(self, attemptAuthorization=True):
        return True

    def downloadURL(self, url, cwd=os.getcwd(), dirname=None, progressCallback=None):
        url_components = GithubClient.GITHUB_URL_PARSER.match(url).group(1).split("/")
        user = url_components[0]
        repo = url_components[1]
        try:
            retrieval_type = url_components[2]
        except IndexError:
            retrieval_type = "tree"
        try:
            branch = url_components[3]
        except IndexError:
            branch = "master"

        if dirname is None:
            dirname = "%s.%s.%s.git" % (user, repo, branch)

        base_dir = os.path.join(cwd, dirname)
        git_url = "git://github.com/%s/%s.git" % (user, repo)

        os.makedirs(base_dir, exist_ok=True)

        gitDriver = git.Git(base_dir)
        gitDriver.clone(git_url, ".")
        gitDriver.checkout(branch)

        # TODO: what goes in the dirs and files keys again?
        return {"local_uri": base_dir, "dirs": {}, "files": []}
