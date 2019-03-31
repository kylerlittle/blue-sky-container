#******************************************************************************
#
#  BlueSky Framework - Controls the estimation of emissions, incorporation of 
#                      meteorology, and the use of dispersion models to 
#                      forecast smoke impacts from fires.
#  Copyright (C) 2003-2006  USDA Forest Service - Pacific Northwest Wildland 
#                           Fire Sciences Laboratory
#  BlueSky Framework - Version 3.5.1    
#  Copyright (C) 2007-2009  USDA Forest Service - Pacific Northwest Wildland Fire 
#                      Sciences Laboratory and Sonoma Technology, Inc.
#                      All rights reserved.
#
# See LICENSE.TXT for the Software License Agreement governing the use of the
# BlueSky Framework - Version 3.5.1.
#
# Contributors to the BlueSky Framework are identified in ACKNOWLEDGEMENTS.TXT
#
#******************************************************************************

_bluesky_version_ = "3.5.1"

from difflib import SequenceMatcher
import os
import sys
from unittest import TestCase
from unittest import TestSuite
from unittest import TextTestRunner
from kernel.config import config
from kernel.core import Process


class OutputTesting(Process):
    """Compares new output files to output files saved in a testing directory."""

    def init(self):
        """All Processes must declare an input node.
        However, this input node is unused."""
        self.declare_input("fires", "FireInformation")

    def run(self, context):
        self.log.info("Running BlueSky Framework tests.\n")

        out_dir = self.config("OUTPUT_DIR")
        test_type = config.get("OutputTesting", "TEST_TYPE")
        test_out_dir = config.get("OutputTesting", "TEST_OUT_DIR")
        files_2_test = config.get("OutputTesting", "FILES_TO_TEST").split()

        if not files_2_test:
            self.log.error('ERROR: No input files were given to the test to compare.')

        # add test to test suite for each file comparison
        suite = TestSuite()
        for file_name in files_2_test:
            out_file_path = os.path.join(out_dir, file_name)
            test_file_path = os.path.join(test_out_dir, file_name)

            suite.addTest(TestFileComparison(test_type, out_file_path, test_file_path))

        # run test suite
        test_results = TextTestRunner(verbosity=2).run(suite)
        if test_results.failures:
            self.log.error('ERROR: BlueSky Framework tests failed.')
            sys.exit(1)

        self.log.info("BlueSky Framework tests complete.")


class TestFileComparison(TestCase):
    """This is a unittest designed to compare two files during runtime."""

    def __init__(self, test_type, output_file, test_file):
        super(TestFileComparison, self).__init__(test_type)
        self.output_file = output_file
        self.test_file = test_file

    def __str__(self):
        return "Testing: %s" % self.output_file

    def test_compare_files(self):
        # open, compare, and close files
        with open(self.test_file, 'rb') as f_test, open(self.output_file, 'rb') as f_out:
            diff = SequenceMatcher(None, f_test.read(), f_out.read())

        # run assert test
        self.assertTrue(diff.ratio() > 0.99, 'Output file ' + self.output_file + ' does not match test file.')

