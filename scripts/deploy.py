# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deployment script for Oppia.

USE THIS SCRIPT AT YOUR OWN RISK! A safe option is to modify app.yaml manually
and run the 'appcfg.py update' command.

This script performs a deployment of Oppia to a Google App Engine appspot
instance. It creates a build with unnecessary files removed, which is saved
in ../deployment_history. It then pushes this build to the production server.

IMPORTANT NOTES:

1.  You will need to first create a folder called ../deploy_data/[APP_NAME],
    where [APP_NAME] is the name of your app as defined in app.yaml. This
    folder should contain a folder called /images, which in turn should contain
    three files: banner.png, favicon.ico and logo.png. These files will be used
    for the splash page of the deployed app.

2.  Before running this script, you must install third-party dependencies by
    running

        bash scripts/start.sh

    at least once.

3.  This script should be run from the oppia root folder:

        python scripts/deploy.py --app_name=[APP_NAME]

    where [APP_NAME] is the name of your app. Note that the root folder MUST be
    named 'oppia'.
"""

import argparse
import datetime
import os
import shutil
import subprocess

_PARSER = argparse.ArgumentParser()
_PARSER.add_argument(
    '--app_name', help='name of the app to deploy to', type=str)

parsed_args = _PARSER.parse_args()
if parsed_args.app_name:
    APP_NAME = parsed_args.app_name
else:
    raise Exception('No app name specified.')

CURRENT_DATETIME = datetime.datetime.utcnow()

RELEASE_DIR_NAME = '%s-deploy-%s' % (
    APP_NAME, CURRENT_DATETIME.strftime('%Y%m%d-%H%M%S'))
RELEASE_DIR_PATH = os.path.join(os.getcwd(), '..', RELEASE_DIR_NAME)

APPCFG_PATH = os.path.join(
    '..', 'oppia_tools', 'google_appengine_1.8.8', 'google_appengine',
    'appcfg.py')

LOG_FILE_PATH = os.path.join('..', 'deploy.log')


class CD(object):
    """Context manager for changing the current working directory."""
    def __init__(self, new_path):
        self.new_path = new_path

    def __enter__(self):
        self.saved_path = os.getcwd()
        os.chdir(self.new_path)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.saved_path)


def ensure_directory_exists(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


def preprocess_release():
    """Pre-processes release files.

    This function should be called from within RELEASE_DIR_NAME. Currently it
    does the following:

    (1) Changes the app name in app.yaml to APP_NAME.
    (2) Substitutes image files for the splash page.
    """
    # Change the app name in app.yaml.
    f = open('app.yaml', 'r')
    content = f.read()
    os.remove('app.yaml')
    content = content.replace('oppiaserver', APP_NAME)
    d = open('app.yaml', 'w+')
    d.write(content)

    # Substitute image files for the splash page.
    SPLASH_PAGE_FILES = ['banner.png', 'favicon.ico', 'logo.png']
    DEPLOY_DATA_PATH = os.path.join(
        os.getcwd(), '..', 'deploy_data', APP_NAME)

    if not os.path.exists(DEPLOY_DATA_PATH):
        raise Exception(
            'Could not find deploy_data directory at %s' % DEPLOY_DATA_PATH)

    for filename in SPLASH_PAGE_FILES:
        src = os.path.join(DEPLOY_DATA_PATH, 'images', filename)
        dst = os.path.join(os.getcwd(), 'static', 'images', filename)
        if not os.path.exists(src):
            raise Exception(
                'Could not find source path %s. Please check your deploy_data '
                'folder.' % src)
        if not os.path.exists(dst):
            raise Exception(
                'Could not find destination path %s. Has the code been '
                'updated in the meantime?' % dst)
        shutil.copyfile(src, dst)


# Check that the current directory is correct.
if not os.getcwd().endswith('oppia'):
    raise Exception('Please run this script from the oppia/ directory.')

print ''
print 'Starting deployment process.'

# Create a folder in which to save the release candidate.
print 'Creating new release directory %s' % RELEASE_DIR_PATH
ensure_directory_exists(RELEASE_DIR_PATH)

# Copy files to the release directory. Omits the .git subfolder.
print 'Copying files to the release directory'
shutil.copytree(
    os.getcwd(), RELEASE_DIR_PATH, ignore=shutil.ignore_patterns('.git'))

# Change the current directory to the release candidate folder.
with CD(RELEASE_DIR_PATH):
    if not os.getcwd().endswith(RELEASE_DIR_NAME):
        raise Exception(
            'Invalid directory accessed during deployment: %s' % os.getcwd())

    print 'Changing directory to %s' % os.getcwd()

    print 'Preprocessing release...'
    preprocess_release()

    # Do a build; ensure there are no errors.
    print 'Building and minifying scripts...'
    subprocess.check_output(['python', 'scripts/build.py'])

    # Run the tests; ensure there are no errors.
    print 'Running tests...'
    subprocess.check_output(['python', 'core/tests/gae_suite.py'])

    # Deploy to GAE.
    subprocess.check_output([APPCFG_PATH, 'update', '.', '--oauth2'])

    # Writing log entry.
    ensure_directory_exists(LOG_FILE_PATH)
    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write('Successfully deployed to %s at %s\n' % (
            APP_NAME, CURRENT_DATETIME.strftime('%Y-%m-%d %H:%M:%S')))

    print 'Returning to oppia/ root directory.'

print 'Done!'