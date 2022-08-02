# Copyright 2021 The SODA Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import six
from oslo_log import log as logging

from delfin import cryptor
from delfin import exception
from delfin.drivers.dell_emc.vplex import consts
from delfin.drivers.utils.rest_client import RestClient

LOG = logging.getLogger(__name__)


class RestHandler(RestClient):

    def __init__(self, **kwargs):
        super(RestHandler, self).__init__(**kwargs)

    def login(self):
        try:
            data = {}
            self.init_http_head()
            self.session.headers.update({
                "username": self.rest_username,
                "password": cryptor.decode(self.rest_password)})
            res = self.do_call(consts.REST_AUTH_URL, data, 'GET')
            if res.status_code != 200:
                LOG.error("Login error. URL: %(url)s\n"
                          "Reason: %(reason)s.",
                          {"url": consts.REST_AUTH_URL, "reason": res.text})
                if 'User authentication failed' in res.text:
                    raise exception.InvalidUsernameOrPassword()
                else:
                    raise exception.StorageBackendException(
                        six.text_type(res.text))
        except Exception as e:
            LOG.error("Login error: %s", six.text_type(e))
            raise e

    def get_rest_info(self, url, data=None, method='GET'):
        """Return dict result of the url response."""
        res = self.do_call(url, data, method)
        return res.json().get('response') if res.status_code == 200 else None

    def get_virtual_volume_by_name_resp(self, cluster_name,
                                        virtual_volume_name):
        url = f'{consts.BASE_CONTEXT}/clusters/{cluster_name}/virtual-volumes/{virtual_volume_name}'

        return self.get_rest_info(url)

    def get_virtual_volume_resp(self, cluster_name):
        url = f'{consts.BASE_CONTEXT}/clusters/{cluster_name}/virtual-volumes'
        return self.get_rest_info(url)

    def get_cluster_resp(self):
        uri = f'{consts.BASE_CONTEXT}/clusters'
        return self.get_rest_info(uri)

    def get_devcie_resp(self, cluster_name):
        url = f'{consts.BASE_CONTEXT}/clusters/{cluster_name}/devices'
        return self.get_rest_info(url)

    def get_device_by_name_resp(self, cluster_name, device_name):
        url = f'{consts.BASE_CONTEXT}/clusters/{cluster_name}/devices/{device_name}'
        return self.get_rest_info(url)

    def get_health_check_resp(self):
        url = f'{consts.BASE_CONTEXT}/health-check'
        data = {"args": "-l"}
        return self.get_rest_info(url, data, method='POST')

    def get_cluster_by_name_resp(self, cluster_name):
        url = f'{consts.BASE_CONTEXT}/clusters/{cluster_name}'
        return self.get_rest_info(url)

    def get_storage_volume_summary_resp(self, cluster_name):
        url = f'{consts.BASE_CONTEXT}/storage-volume+summary'
        args = f'--clusters {cluster_name}'
        data = {"args": args}
        return self.get_rest_info(url, data, method='POST')

    def get_device_summary_resp(self, cluster_name):
        url = f'{consts.BASE_CONTEXT}/local-device+summary'
        args = f'--clusters {cluster_name}'
        data = {"args": args}
        return self.get_rest_info(url, data, method='POST')

    def get_virtual_volume_summary_resp(self, cluster_name):
        url = f'{consts.BASE_CONTEXT}/virtual-volume+summary'
        args = f'--clusters {cluster_name}'
        data = {"args": args}
        return self.get_rest_info(url, data, method='POST')

    def logout(self):
        try:
            if self.session:
                self.session.close()
        except Exception as e:
            err_msg = f"Logout error: {six.text_type(e)}"
            LOG.error(err_msg)
            raise e

    def get_engine_director_resp(self):
        url = f'{consts.BASE_CONTEXT}/engines/*/directors/*'
        return self.get_rest_info(url)

    def get_version_verbose(self):
        url = f'{consts.BASE_CONTEXT}/version'
        args = '-a --verbose'
        data = {"args": args}
        return self.get_rest_info(url, data, method='POST')

    def get_cluster_export_port_resp(self):
        url = f'{consts.BASE_CONTEXT}/clusters/*/exports/ports/*'
        return self.get_rest_info(url)

    def get_engine_director_hardware_port_resp(self):
        url = f'{consts.BASE_CONTEXT}/engines/*/directors/*/hardware/ports/*'
        return self.get_rest_info(url)
