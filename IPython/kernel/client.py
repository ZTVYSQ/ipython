"""Base class to manage the interaction with a running kernel
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2013  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

from __future__ import absolute_import

import zmq

# Local imports
from IPython.config.configurable import LoggingConfigurable
from IPython.utils.traitlets import (
    Any, Instance, Type,
)

from .zmq.session import Session
from .channels import (
    ShellChannel, IOPubChannel,
    HBChannel, StdInChannel,
)
from .clientabc import KernelClientABC
from .connect import ConnectionFileMixin


#-----------------------------------------------------------------------------
# Main kernel client class
#-----------------------------------------------------------------------------

class KernelClient(LoggingConfigurable, ConnectionFileMixin):
    """Communicates with a single kernel on any host via zmq channels.

    There are four channels associated with each kernel:

    * shell: for request/reply calls to the kernel.
    * iopub: for the kernel to publish results to frontends.
    * hb: for monitoring the kernel's heartbeat.
    * stdin: for frontends to reply to raw_input calls in the kernel.

    """

    # The PyZMQ Context to use for communication with the kernel.
    context = Instance(zmq.Context)
    def _context_default(self):
        return zmq.Context.instance()

    # The Session to use for communication with the kernel.
    session = Instance(Session)
    def _session_default(self):
        return Session(config=self.config)

    # The classes to use for the various channels
    shell_channel_class = Type(ShellChannel)
    iopub_channel_class = Type(IOPubChannel)
    stdin_channel_class = Type(StdInChannel)
    hb_channel_class = Type(HBChannel)

    # Protected traits
    _shell_channel = Any
    _iopub_channel = Any
    _stdin_channel = Any
    _hb_channel = Any

    #--------------------------------------------------------------------------
    # Channel management methods
    #--------------------------------------------------------------------------

    def start_channels(self, shell=True, iopub=True, stdin=True, hb=True):
        """Starts the channels for this kernel.

        This will create the channels if they do not exist and then start
        them (their activity runs in a thread). If port numbers of 0 are
        being used (random ports) then you must first call
        :method:`start_kernel`. If the channels have been stopped and you
        call this, :class:`RuntimeError` will be raised.
        """
        if shell:
            self.shell_channel.start()
        if iopub:
            self.iopub_channel.start()
        if stdin:
            self.stdin_channel.start()
            self.shell_channel.allow_stdin = True
        else:
            self.shell_channel.allow_stdin = False
        if hb:
            self.hb_channel.start()

    def stop_channels(self):
        """Stops all the running channels for this kernel.

        This stops their event loops and joins their threads.
        """
        if self.shell_channel.is_alive():
            self.shell_channel.stop()
        if self.iopub_channel.is_alive():
            self.iopub_channel.stop()
        if self.stdin_channel.is_alive():
            self.stdin_channel.stop()
        if self.hb_channel.is_alive():
            self.hb_channel.stop()

    @property
    def channels_running(self):
        """Are any of the channels created and running?"""
        return (self.shell_channel.is_alive() or self.iopub_channel.is_alive() or
                self.stdin_channel.is_alive() or self.hb_channel.is_alive())

    def _make_url(self, port):
        """Make a zmq url with a port.

        There are two cases that this handles:

        * tcp: tcp://ip:port
        * ipc: ipc://ip-port
        """
        if self.transport == 'tcp':
            return "tcp://%s:%i" % (self.ip, port)
        else:
            return "%s://%s-%s" % (self.transport, self.ip, port)

    @property
    def shell_channel(self):
        """Get the shell channel object for this kernel."""
        if self._shell_channel is None:
            self._shell_channel = self.shell_channel_class(
                self.context, self.session, self._make_url(self.shell_port)
            )
        return self._shell_channel

    @property
    def iopub_channel(self):
        """Get the iopub channel object for this kernel."""
        if self._iopub_channel is None:
            self._iopub_channel = self.iopub_channel_class(
                self.context, self.session, self._make_url(self.iopub_port)
            )
        return self._iopub_channel

    @property
    def stdin_channel(self):
        """Get the stdin channel object for this kernel."""
        if self._stdin_channel is None:
            self._stdin_channel = self.stdin_channel_class(
                self.context, self.session, self._make_url(self.stdin_port)
            )
        return self._stdin_channel

    @property
    def hb_channel(self):
        """Get the hb channel object for this kernel."""
        if self._hb_channel is None:
            self._hb_channel = self.hb_channel_class(
                self.context, self.session, self._make_url(self.hb_port)
            )
        return self._hb_channel

    def is_alive(self):
        """Is the kernel process still running?"""
        if self._hb_channel is not None:
            # We didn't start the kernel with this KernelManager so we
            # use the heartbeat.
            return self._hb_channel.is_beating()
        else:
            # no heartbeat and not local, we can't tell if it's running,
            # so naively return True
            return True


#-----------------------------------------------------------------------------
# ABC Registration
#-----------------------------------------------------------------------------

KernelClientABC.register(KernelClient)
