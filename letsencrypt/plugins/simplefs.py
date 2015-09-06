"""SimpleFS plugin."""
import errno
import logging
import os

import zope.interface

from acme import challenges

from letsencrypt import errors
from letsencrypt import interfaces
from letsencrypt.plugins import common


logger = logging.getLogger(__name__)


class Authenticator(common.Plugin):
    """SimpleFS Authenticator."""
    zope.interface.implements(interfaces.IAuthenticator)
    zope.interface.classProvides(interfaces.IPluginFactory)

    description = "SimpleFS Authenticator"

    MORE_INFO = """\
Authenticator plugin that performs SimpleHTTP challenge by saving
necessary validation resources to appropriate paths on the file
system. It expects that there is some other HTTP server configured
to serve all files under specified web root ({0})."""

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return self.MORE_INFO.format(self.conf("root"))

    @classmethod
    def add_parser_arguments(cls, add):
        add("root", help="public_html / webroot path")

    def get_chall_pref(self, domain):
        # pylint: disable=missing-docstring,no-self-use,unused-argument
        return [challenges.SimpleHTTP]

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)

        root = self.conf("root")
        if root is None:
            raise errors.Error("--{0} must be set".format(
                self.option_name("root")))
        if not os.path.isdir(root):
            raise errors.Error(root + " does not exist or is not a directory")
        self.full_root = os.path.join(
            root, challenges.SimpleHTTPResponse.URI_ROOT_PATH)

    def prepare(self):  # pylint: disable=missing-docstring
        logger.debug("Creating root challenges validation dir at %s",
                     self.full_root)
        try:
            os.makedirs(self.full_root)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

    def perform(self, achalls):  # pylint: disable=missing-docstring
        return [self._perform_single(achall) for achall in achalls]

    def _path_for_achall(self, achall):
        return os.path.join(self.full_root, achall.chall.encode("token"))

    def _perform_single(self, achall):
        response, validation = achall.gen_response_and_validation(
            tls=(not self.config.no_simple_http_tls))
        path = self._path_for_achall(achall)
        logger.debug("Attempting to save validation to %s", path)
        with open(path, "w") as validation_file:
            validation_file.write(validation.json_dumps())
        return response

    def cleanup(self, achalls):  # pylint: disable=missing-docstring
        for achall in achalls:
            path = self._path_for_achall(achall)
            logger.debug("Removing %s", path)
            os.remove(path)
