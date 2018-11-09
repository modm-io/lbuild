#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import logging.config


def configure_logger(verbosity):
    """
    Load the default configuration for the logger.
    """
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'full': {
                # 'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                'format': '[%(levelname)s] %(name)s: %(message)s'
            },
            'simple': {
                'format': '%(message)s'
            },
        },
        'handlers': {
            'default': {
                'class':'logging.StreamHandler',
                'formatter': 'full',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'DEBUG' if verbosity > 1 else ('INFO' if verbosity == 1 else 'WARNING'),
                'propagate': True
            }
        }
    })
