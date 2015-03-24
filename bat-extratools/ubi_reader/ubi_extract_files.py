#!/usr/bin/env python
#############################################################
# ubi_reader
# (c) 2013 Jason Pruitt (jrspruitt@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#############################################################

import os
import sys
import time
import argparse

from modules import settings
from modules.ubi import ubi
from modules.ubi.defines import UBI_EC_HDR_MAGIC
from modules.ubifs import ubifs
from modules.ubifs.output import extract_files
from modules.ubifs.defines import UBIFS_NODE_MAGIC
from modules.ubi_io import ubi_file, leb_virtual_file
from modules.debug import error, log
from modules.utils import guess_filetype, guess_start_offset, guess_leb_size, guess_peb_size

def create_output_dir(outpath):
    if os.path.exists(outpath):
        if os.listdir(outpath):
            error(create_output_dir, 'Fatal', 'Output directory is not empty. %s' % outpath)
    else:
        try:
            os.makedirs(outpath)
            log(create_output_dir, 'Created output path: %s' % outpath)
        except Exception, e:
            error(create_output_dir, 'Fatal', '%s' % e)


if __name__=='__main__':
    start = time.time()
    description = 'Extract contents of a UBI or UBIFS image.'
    usage = 'extract_files.py [options] filepath'
    parser = argparse.ArgumentParser(usage=usage, description=description)

    parser.add_argument('-k', '--keep-permissions', action='store_true', dest='permissions',
                      help='Maintain file permissions, requires running as root. (default: False)')

    parser.add_argument('-l', '--log', action='store_true', dest='log',
                      help='Print extraction information to screen.')

    parser.add_argument('-v', '--verbose-log', action='store_true', dest='verbose',
                      help='Prints nearly everything about anything to screen.')
    
    parser.add_argument('-p', '--peb-size', type=int, dest='block_size',
                        help='Specify PEB size. (UBI Only)')
    
    parser.add_argument('-e', '--leb-size', type=int, dest='block_size',
                        help='Specify LEB size. (UBIFS Only)')

    parser.add_argument('-s', '--start-offset', type=int, dest='start_offset',
                        help='Specify offset of UBI/UBIFS data in file. (default: 0)')

    parser.add_argument('-n', '--end-offset', type=int, dest='end_offset',
                        help='Specify end offset of UBI/UBIFS data in file.')

    parser.add_argument('-o', '--output-dir', dest='outpath',
                        help='Specify output directory path.')

    parser.add_argument('filepath', help='File to extract contents of.')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.filepath:
        path = args.filepath
        if not os.path.exists(path):
            parser.error("File path doesn't exist.")

    if args.start_offset:
        start_offset = args.start_offset
    else:
        start_offset = guess_start_offset(path)

    if args.end_offset:
        end_offset = args.end_offset
    else:
        end_offset = None

    filetype = guess_filetype(path, start_offset)
    if not filetype:
        parser.error('Could not determine file type.')

    img_name = os.path.basename(path)
    if args.outpath:
        outpath = os.path.abspath(os.path.join(args.outpath, img_name))
    else:
        outpath = os.path.join(settings.output_dir, img_name)

    settings.logging_on = args.log

    settings.logging_on_verbose = args.verbose

    if args.block_size:
        block_size = args.block_size
    else:
        if filetype == UBI_EC_HDR_MAGIC:
            block_size = guess_peb_size(path)
        elif filetype == UBIFS_NODE_MAGIC:
            block_size = guess_leb_size(path)

        if not block_size:
            parser.error('Block size could not be determined.')

    perms = args.permissions

    # Create file object.
    ufile_obj = ubi_file(path, block_size, start_offset, end_offset)

    if filetype == UBI_EC_HDR_MAGIC:
        # Create UBI object
        ubi_obj = ubi(ufile_obj)

        # Loop through found images in file.
        for image in ubi_obj.images:

            # Create path for specific image
            # In case multiple images in data
            img_outpath = os.path.join(outpath, '%s' % image.image_seq)

            # Loop through volumes in each image.
            for volume in image.volumes:
                    
                # Get blocks associated with this volume.
                vol_blocks = image.volumes[volume].get_blocks(ubi_obj.blocks)

                # Create volume data output path.
                vol_outpath = os.path.join(img_outpath, volume)
                
                # Create volume output path directory.
                create_output_dir(vol_outpath)

                # Skip volume if empty.
                if not len(vol_blocks):
                    continue

                # Create LEB backed virtual file with volume blocks.
                # Necessary to prevent having to load entire UBI image
                # into memory.
                lebv_file = leb_virtual_file(ubi_obj, vol_blocks)

                # Extract files from UBI image.
                ubifs_obj = ubifs(lebv_file)
                print 'Extracting files to: %s' % vol_outpath
                extract_files(ubifs_obj, vol_outpath, perms)


    elif filetype == UBIFS_NODE_MAGIC:
        # Create UBIFS object
        ubifs_obj = ubifs(ufile_obj)

        # Create directory for files.
        create_output_dir(outpath)

        # Extract files from UBIFS image.
        print 'Extracting files to: %s' % outpath
        extract_files(ubifs_obj, outpath, perms)

    else:
        print 'Something went wrong to get here.'