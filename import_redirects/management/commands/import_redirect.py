from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist
from django.utils.six.moves import input
from django.db import transaction
from django.contrib.redirects.models import Redirect
from django.conf import settings
from optparse import make_option

import os
import csv
import re
import logging

VALID_URL = re.compile("^\/$|(?:\/[\w\.,\-\?\+&=#:\]\[!@\$%\^\*\(\)~<>]+)+\/?$")
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s')


class Command(BaseCommand):
    help = 'Import redirects from csv-file'

    option_list = BaseCommand.option_list + (
        make_option('-f', '--file', action='store', type='string', dest='filename',
                    help='Path to csv-file. Delimiter: ";"'),
        make_option('-l', '--log', action='store', type='string', dest='logfile', help='Path to log-file'),
        make_option('--change', action='store_true', dest='change', help='Change new_path for existing redirects')
    )
    can_import_settings = True

    def handle(self, *args, **options):
        logfile = options.get('logfile')
        if logfile:
            handler = logging.FileHandler(logfile)
            handler.setLevel(logging.INFO)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        if not options.get('filename'):
            raise CommandError('You must provide path to csv-file. Use -f option.')
        path_to_file = os.path.normpath(options.get('filename'))
        if not os.path.exists(path_to_file):
            raise CommandError('File not found')
        if os.path.isdir(path_to_file):
            raise CommandError('%s is a directory' %path_to_file)
        dirname = os.path.dirname(path_to_file)
        start = os.path.join(dirname, "import_start")
        finish = os.path.join(dirname, "import_finish")
        if not os.path.exists(start):
            f = open(start, 'w')
            f.close()
        if os.path.exists(finish):
            os.remove(finish)
        with open(path_to_file, 'rb') as csvfile:
            data = csv.DictReader(csvfile, fieldnames=['old_path', 'new_path'], delimiter=';')
            with transaction.commit_on_success():
                for i, row in enumerate(data):
                    old_path = row['old_path']
                    new_path = row['new_path']
                    if not VALID_URL.match(old_path):
                        mess = 'LINE: %s. Invalid url: %s' %(i+1, old_path)
                        if logfile:
                            logger.error(mess)
                        f = open(finish, 'w')
                        f.close()
                        raise Exception(mess)
                    if not VALID_URL.match(new_path):
                        mess = 'LINE: %s. Invalid url: %s' %(i+1, new_path)
                        if logfile:
                            logger.error(mess)
                        f = open(finish, 'w')
                        f.close()
                        raise Exception(mess)
                    try:
                        redirect = Redirect.objects.get(site_id=settings.SITE_ID, old_path=old_path)
                        if redirect.new_path != new_path:
                            change = ""
                            if not options.get('change'):
                                self.stdout.write('\nRedirect %s exist. Change to %s ---> %s ?:\n'
                                                  %(redirect.__unicode__(), old_path, new_path))
                                change = input('"y" for Yes or "n" for No (leave blank for "n"): ')
                            if change == "y" or options.get('change'):
                                redirect.new_path = new_path
                                redirect.save()
                    except ObjectDoesNotExist:
                        Redirect.objects.create(site_id=settings.SITE_ID, old_path=old_path, new_path=new_path)
        f = open(finish, 'w')
        f.close()
        if logfile:
            logger.info('Import completed successfully')
        else:
            self.stdout.write("Import completed successfully\n")
