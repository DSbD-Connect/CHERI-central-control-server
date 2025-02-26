#!/bin/bash


source /morello/env/morello-sdk

clang -march=morello --target=aarch64-linux-musl_purecap --sysroot=${MUSL_HOME} command_handler.c -o command_handler_cheri -static

clang --target=aarch64-linux-gnu --sysroot=/root/musl-aarch64/musl-install command_handler.c -o command_handler_nocheri -static



