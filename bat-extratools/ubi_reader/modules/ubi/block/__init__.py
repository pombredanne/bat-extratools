#!/usr/bin/env python
#############################################################
# ubi_reader/ubi
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

import re
from modules import settings
from modules.debug import error, log, verbose_display, verbose_log
from modules.ubi import display
from modules.ubi.defines import UBI_EC_HDR_SZ, UBI_VID_HDR_SZ, UBI_INTERNAL_VOL_START, UBI_EC_HDR_MAGIC
from modules.ubi.headers import ec_hdr, vid_hdr, vtbl_recs


class description(object):
    """UBI Block description Object

    UBI Specifications:
    http://www.linux-mtd.infradead.org/  -- Home page
    <kernel>/drivers/mtd/ubi/ubi-media.h -- Header structs
                                            and defines

    Attributes:
    Obj:ec_hdr           -- Error Count Header
    Obj:vid_hdr          -- Volume ID Header
    List:vtbl_recs       -- (Optional) List of Volume Table Records.
    Bool:is_vtbl         -- If contains volume records table.
    Bool:is_internal_vol -- If Vol ID is > UBI_INTERNAL_VOL_START
    Bool:is_valid        -- If ec_hdr & vid_hdr are error free.
    Int:peb_num          -- Physical Erase Block number.
    Int:leb_num          -- Logical Erase Block number.
    Int:file_offset      -- Address location in file of this block.
    Int:size             -- Size of total block data or PEB size.
    Will print out all information when invoked as a string.
    """

    def __init__(self, block_buf):
 
        self.file_offset = -1
        self.peb_num = -1
        self.leb_num = -1
        self.size = -1

        self.vid_hdr = None
        self.is_internal_vol = False
        self.vtbl_recs = []

        # TODO better understanding of block types/errors
        self.ec_hdr = ec_hdr(block_buf[0:UBI_EC_HDR_SZ])

        if not self.ec_hdr.errors or settings.ignore_block_errors:
            self.vid_hdr = vid_hdr(block_buf[self.ec_hdr.vid_hdr_offset:self.ec_hdr.vid_hdr_offset+UBI_VID_HDR_SZ])

            if not self.vid_hdr.errors or settings.ignore_block_errors:
                self.is_internal_vol = self.vid_hdr.vol_id >= UBI_INTERNAL_VOL_START
    
                if self.vid_hdr.vol_id >= UBI_INTERNAL_VOL_START:
                    self.vtbl_recs = vtbl_recs(block_buf[self.ec_hdr.data_offset:])
    
                self.leb_num = self.vid_hdr.lnum
        self.is_vtbl = bool(self.vtbl_recs) or False
        self.is_valid = not self.ec_hdr.errors and not self.vid_hdr.errors or settings.ignore_block_errors


    def __repr__(self):
        return 'Block: PEB# %s: LEB# %s' % (self.peb_num, self.leb_num)


    def display(self, tab=''):
        return display.block(self, tab)



def get_blocks_in_list(blocks, idx_list):
    """Retrieve block objects in list of indexes

    Arguments:
    List:blocks   -- List of block objects
    List:idx_list -- List of block indexes

    Returns:
    Dict:blocks   -- List of block objects generated
                     from provided list of indexes in
                     order of idx_list.
    """

    return {i:blocks[i] for i in idx_list}



def extract_blocks(ubi):
    """Get a list of UBI block objects from file

    Arguments:.
    Obj:ubi    -- UBI object.
    
    Returns:
    Dict -- Of block objects keyed by PEB number.
    """

    blocks = {}
    ubi.file.seek(ubi.file.start_offset)
    peb_count = 0
    cur_offset = 0
    
    # range instead of xrange, as xrange breaks > 4GB end_offset.
    for i in range(ubi.file.start_offset, ubi.file.end_offset, ubi.file.block_size):
        buf = ubi.file.read(ubi.file.block_size)

        if buf.startswith(UBI_EC_HDR_MAGIC):
            blk = description(buf)
            blk.file_offset = i
            blk.peb_num = ubi.first_peb_num + peb_count
            blk.size = ubi.file.block_size
            blocks[blk.peb_num] = blk
            peb_count += 1
            log(extract_blocks, blk)
            verbose_log(extract_blocks, 'file addr: %s' % (ubi.file.last_read_addr()))
            verbose_display(blk)      
        else:
            cur_offset += ubi.file.block_size
            ubi.first_peb_num = cur_offset/ubi.file.block_size
            ubi.file.start_offset = cur_offset

    return blocks
