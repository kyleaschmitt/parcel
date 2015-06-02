from cmd2 import Cmd, options, make_option
import os
import manifest
from http_client import HTTPClient
import defaults
import shlex
import const


HEADER = """parcel - High Performance Download Client - Interactive mode
Type 'help' for a list of commands or 'help <topic>' for detailed usage.
* Add files to download with 'manifest' or 'add' and start download with 'download'.
"""

TIPS = """
TIPS:
- Rather than type out path names, try dragging and dropping manifest and token files into the terminal.
- You can execute shell commands by prepending '!', i.e. !ls.
- You can run the parcel binary with advanced options from the command line (parcel --help).
"""

BASIC_COMMANDS = """Basic commands are:
- download   (download files in registry)
- add        (adds ids to registry)
- list       (lists file ids already registered)
- manifest   (add ids from a GDC manifest file to registry)
- remove     (remove ids from registry)
- token      (load an authorization token file)
- cd         (move to directory you want to download to)
- pwd        (print the current working directory)
- set        (set advanced configuration setting)
- settings   (list advanced configuration settings)
"""


class ParcelREPL(Cmd):

    def __init__(self, *args, **kwargs):
        self.file_ids = set()
        self.token = None
        Cmd.__init__(self, *args, **kwargs)
        print(HEADER)
        print(BASIC_COMMANDS)
        print(TIPS)

        self.settings = dict(
            server=defaults.url,
            protocol='tcp',
            processes=defaults.processes,
            save_interval=const.SAVE_INTERVAL,
            http_chunk_size=const.HTTP_CHUNK_SIZE,
        )

    def _add_ids(self, ids):
        if not ids:
            return
        start_len = len(self.file_ids)
        map(self.file_ids.add, ids)
        end_len = len(self.file_ids)
        print(("Loaded {} new file ids.  There are {} file ids to download.\n"
               "Start download with 'download'.  List ids with 'list'").format(
                   end_len - start_len, end_len))

    def _remove_ids(self, ids):
        if not ids:
            return
        start_len = len(self.file_ids)
        for fid in ids:
            try:
                self.file_ids.remove(fid)
            except Exception as msg:
                print('Unable to remove id {}: {}'.format(fid, msg))
        end_len = len(self.file_ids)
        print(("Removed {} file ids from registry.\n"
               "There are {} file ids left to download.\n"
               "Start download with 'download'.  List ids with 'list'").format(
                   start_len - end_len, end_len))

    def do_manifest(self, manifest_path):
        if not manifest_path:
            print('No manifest specified to load.')
            self.help_manifest()
            return
        with open(manifest_path, 'r') as fd:
            self._add_ids([f['id'] for f in manifest.parse(fd)])

    def help_manifest(self):
        print('manifest <path_to_file>')
        print('Load file ids from a manifest')

    def do_token(self, token_path):
        if not token_path:
            print('No token specified to load.')
            if self.token:
                print('Previously loaded token ({} bytes).'.format(
                    len(self.token)))
            else:
                print('No token previously loaded')
            return
        with open(token_path, 'r') as f:
            self.token = f.read().strip()
        print('Loaded token ({} bytes).'.format(len(self.token)))

    def help_token(self):
        print("token <path_to_file>")
        print("Load your token from a file.  "
              "This token will be used to authenticate you when "
              "downloading protected data.")

    def do_list(self, arg):
        if not self.file_ids:
            print("No files to download.  Add files with 'manifest' or 'add'.")
        else:
            print('File ids schedule to download:')
            for fid in self.file_ids:
                print(' - {}'.format(fid))

    def help_list(self):
        print("\tList all ids registered to download. Start download with 'download'")

    def do_add(self, arg):
        ids = shlex.split(arg)
        if not ids:
            print('No ids specified.')
            self.help_add()
            return
        self._add_ids(ids)

    def help_add(self):
        print("add <id1> <id2>")
        print("Register ids to register to download.")
        print("Enter each id separated by a space.")

    def do_remove(self, arg):
        ids = shlex.split(arg)
        if not ids:
            print('No ids specified.')
            self.help_remove()
            return
        self._remove_ids(ids)

    def help_remove(self):
        print('remove:')
        print("remove <id1> <id2>")
        print("Register ids to remove from registry.")
        print("Use 'clear' to remove all ids from registry.")

    def do_clear(self, arg):
        self.file_ids = set()
        print('Cleared registered file ids.')

    def help_clear(self):
        print("\tRemove all registered ids.")

    def do_clear_token(self, arg):
        self.token = None
        print("Cleared authorization token.")

    def help_clear_token(self):
        print("Clears the authorization token.")

    def do_cd(self, path):
        os.chdir(os.path.expanduser(path))
        print('Changed working directory to {}'.format(os.getcwd()))

    def do_pwd(self, path):
        print(os.getcwd())

    def help_pwd(self, path):
        print('Print the current working directory.')

    @options([
        make_option('-m', '--manifest', help="a manifest file to load ids from"),
        make_option('-t', '--token', help="a token file to load"),
    ])
    def do_download(self, arg, opts=None):
        manifest_path = opts.get('manifest')
        token_path = opts.get('token')
        if manifest_path:
            self.do_manifest(manifest_path)
        if token_path:
            self.do_token(token_path)
        if not self.file_ids:
            self.do_list(None)
            return
        if self.settings['protocol'] == 'tcp':
            client = HTTPClient(
                token=self.token,
                n_procs=int(self.settings['processes']),
                directory=os.path.abspath(os.getcwd()),
                uri=self.settings['server'],
                http_chunk_size=int(self.settings['http_chunk_size']),
                save_interval=int(self.settings['save_interval']),
            )
        else:
            raise RuntimeError(
                '{} protocol not supported in interactive mode'.format(
                    self.settings['protocol']))
        downloaded, errors = client.download_files(self.file_ids)
        self._remove_ids(downloaded)

    def help_download(self):
        print('Will start downloading ids registered')

    def do_help(self, arg):
        if not arg:
            print(HEADER)
            print(BASIC_COMMANDS)
        Cmd.do_help(self, arg)

    def do_set(self, arg):
        attr, value = shlex.split(arg)
        if attr not in self.settings:
            raise ValueError(
                "{} not a valid setting. Try 'settings'.".format(attr))
        print("Updating {} from '{}' to '{}'".format(
            attr, self.settings[attr], value))
        self.settings[attr] = value

    def help_set(self):
        print("set <setting> <new value>")
        print("Change an advanced setting from default.")
        print("Try 'settings' to see available settings.")

    def do_settings(self, arg):
        print('-- Settings --')
        for key, val in self.settings.iteritems():
            print('{}: {}'.format(key, val))

    def do_show(self, arg):
        self.do_settings(arg)

    def do_commands(self, arg):
        self.do_help(arg)

    def help_commands(self):
        print('Alias for help.')
