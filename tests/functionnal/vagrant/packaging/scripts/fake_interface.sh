#!/usr/bin/sh -eux

ip link show fake_interface || ip l a fake_interface type dummy
