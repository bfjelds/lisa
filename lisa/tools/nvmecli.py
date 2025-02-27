# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
import re
from typing import cast

from lisa.executable import Tool
from lisa.operating_system import Posix
from lisa.tools import Git, Make
from lisa.util import find_patterns_in_lines
from lisa.util.process import ExecutableResult


class Nvmecli(Tool):
    repo = "https://github.com/linux-nvme/nvme-cli"
    # error_count\t: 0
    __error_count_pattern = re.compile(r"^error_count.*:[ ]+([\d]+)\r?$", re.M)
    # [3:3] : 0     NS Management and Attachment Supported
    __ns_management_attachement_support = "NS Management and Attachment Supported"
    # [1:1] : 0x1   Format NVM Supported
    __format_device_support = "Format NVM Supported"
    # Higher version nvme-cli add a mandatory parameter `--block-size` after
    #  v1.6 (not included)
    # https://github.com/linux-nvme/nvme-cli/blob/v1.7/nvme.c#L3040
    # FLBAS corresponding to block size 0 not found
    # Please correct block size, or specify FLBAS directly
    __missing_block_size_parameter = "FLBAS corresponding to block size 0 not found"

    @property
    def command(self) -> str:
        return "nvme"

    @property
    def can_install(self) -> bool:
        return True

    def _install_from_src(self) -> None:
        posix_os: Posix = cast(Posix, self.node.os)
        posix_os.install_packages([Git, Make, "pkg-config"])
        tool_path = self.get_tool_path()
        git = self.node.tools[Git]
        git.clone(self.repo, tool_path)
        make = self.node.tools[Make]
        code_path = tool_path.joinpath("nvme-cli")
        make.make_install(cwd=code_path)

    def create_namespace(self, namespace: str) -> ExecutableResult:
        cmd_result = self.run(f"create-ns {namespace}", shell=True, sudo=True)
        if self.__missing_block_size_parameter in cmd_result.stdout:
            cmd_result = self.run(
                f"create-ns {namespace} --block-size 4096", shell=True, sudo=True
            )
        return cmd_result

    def delete_namespace(self, namespace: str, id_: int) -> ExecutableResult:
        return self.run(f"delete-ns -n {id_} {namespace}", shell=True, sudo=True)

    def detach_namespace(self, namespace: str, id_: int) -> ExecutableResult:
        return self.run(f"detach-ns -n {id_} {namespace}", shell=True, sudo=True)

    def format_namespace(self, namespace: str) -> ExecutableResult:
        return self.run(f"format {namespace}", shell=True, sudo=True)

    def install(self) -> bool:
        if not self._check_exists():
            posix_os: Posix = cast(Posix, self.node.os)
            package_name = "nvme-cli"
            posix_os.install_packages(package_name)
            if not self._check_exists():
                self._install_from_src()
        return self._check_exists()

    def get_error_count(self, namespace: str) -> int:
        error_log = self.run(f"error-log {namespace}", shell=True, sudo=True)
        error_count = 0
        # for row in error_log.stdout.splitlines():
        errors = find_patterns_in_lines(error_log.stdout, [self.__error_count_pattern])
        if errors[0]:
            error_count = sum([int(element) for element in errors[0]])
        return error_count

    def support_ns_manage_attach(self, device_name: str) -> bool:
        cmd_result = self.run(f"id-ctrl -H {device_name}", shell=True, sudo=True)
        cmd_result.assert_exit_code()
        return self.__ns_management_attachement_support in cmd_result.stdout

    def support_device_format(self, device_name: str) -> bool:
        cmd_result = self.run(f"id-ctrl -H {device_name}", shell=True, sudo=True)
        cmd_result.assert_exit_code()
        return self.__format_device_support in cmd_result.stdout
