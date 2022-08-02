# Copyright 2021 The SODA Authors.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import threading

import requests
import six
from oslo_log import log as logging

from delfin import cryptor
from delfin import exception
from delfin.drivers.hitachi.vsp import consts
from delfin.drivers.utils.rest_client import RestClient

LOG = logging.getLogger(__name__)


class RestHandler(RestClient):
    COMM_URL = '/ConfigurationManager/v1/objects/storages'
    LOGOUT_URL = '/ConfigurationManager/v1/objects/sessions/'

    AUTH_KEY = 'Authorization'

    def __init__(self, **kwargs):
        super(RestHandler, self).__init__(**kwargs)
        self.session_lock = threading.Lock()
        self.session_id = None
        self.storage_device_id = None
        self.device_model = None
        self.serial_number = None

    def call(self, url, data=None, method=None,
             calltimeout=consts.SOCKET_TIMEOUT):
        try:
            res = self.call_with_token(url, data, method, calltimeout)
            if res.status_code in [
                consts.ERROR_SESSION_INVALID_CODE,
                consts.ERROR_SESSION_IS_BEING_USED_CODE,
            ]:
                LOG.error("Failed to get token=={0}=={1},get token again"
                          .format(res.status_code, res.text))
                # if method is logout,return immediately
                if method == 'DELETE' and RestHandler. \
                            LOGOUT_URL in url:
                    return res
                if self.get_token():
                    res = self.call_with_token(url, data, method, calltimeout)
                else:
                    LOG.error('Login error,get access_session failed')
            elif res.status_code == 503:
                raise exception.InvalidResults(res.text)

            return res

        except Exception as e:
            err_msg = f"Get RestHandler.call failed: {six.text_type(e)}"
            LOG.error(err_msg)
            raise e

    def call_with_token(self, url, data, method, calltimeout):
        auth_key = None
        if self.session:
            auth_key = self.session.headers.get(RestHandler.AUTH_KEY, None)
            if auth_key:
                self.session.headers[RestHandler.AUTH_KEY] \
                    = cryptor.decode(auth_key)
        res = self. \
            do_call(url, data, method, calltimeout)
        if auth_key:
            self.session.headers[RestHandler.AUTH_KEY] = auth_key
        return res

    def get_rest_info(self, url, timeout=consts.SOCKET_TIMEOUT, data=None):
        if self.session and url != RestHandler.COMM_URL:
            auth_key = self.session.headers.get(RestHandler.AUTH_KEY, None)
            if auth_key is None:
                self.get_token()
        res = self.call(url, data, 'GET', timeout)
        return res.json() if res.status_code == 200 else None

    def get_token(self):
        try:
            succeed = False
            if self.san_address:
                url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/sessions'
                data = {}

                with self.session_lock:
                    if self.session is None:
                        self.init_http_head()
                    self.session.auth = \
                            requests.auth.HTTPBasicAuth(
                            self.rest_username,
                            cryptor.decode(self.rest_password))
                    res = self.call_with_token(url, data, 'POST', 30)
                    if res.status_code == 200:
                        succeed = True
                        result = res.json()
                        self.session_id = cryptor.encode(
                            result.get('sessionId'))
                        access_session = f"Session {result.get('token')}"
                        self.session.headers[
                            RestHandler.AUTH_KEY] = cryptor.encode(
                            access_session)
                    else:
                        LOG.error("Login error. URL: %(url)s\n"
                                  "Reason: %(reason)s.",
                                  {"url": url, "reason": res.text})
                        if 'authentication failed' in res.text:
                            raise exception.InvalidUsernameOrPassword()
                        elif 'KART30005-E' in res.text:
                            raise exception.StorageBackendException(
                                six.text_type(res.text))
                        else:
                            raise exception.BadResponse(res.text)
            else:
                LOG.error('Token Parameter error')

            return succeed
        except Exception as e:
            LOG.error("Get token error: %s", six.text_type(e))
            raise e

    def login(self):
        try:
            succeed = False
            succeed = self.get_device_id()
            return succeed
        except Exception as e:
            LOG.error("Login error: %s", six.text_type(e))
            raise e

    def logout(self):
        try:
            url = RestHandler.LOGOUT_URL
            if self.session_id is not None:
                url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/sessions/{cryptor.decode(self.session_id)}'

                if self.san_address:
                    self.call(url, method='DELETE')
                    url = None
                    self.session_id = None
                    self.storage_device_id = None
                    self.device_model = None
                    self.serial_number = None
                    self.session = None
            else:
                LOG.error('logout error:session id not found')
        except Exception as err:
            LOG.error(f'logout error:{err}')
            raise exception.StorageBackendException(
                reason='Failed to Logout from restful')

    def get_device_id(self):
        try:
            succeed = False
            if self.session is None:
                self.init_http_head()
            storage_systems = self.get_system_info()
            system_info = storage_systems.get('data')
            for system in system_info:
                succeed = True
                if system.get('model') in consts.SUPPORTED_VSP_SERIES:
                    if system.get('ctl1Ip') == self.rest_host or \
                                system.get('ctl2Ip') == self.rest_host:
                        self.storage_device_id = system.get('storageDeviceId')
                        self.device_model = system.get('model')
                        self.serial_number = system.get('serialNumber')
                        break
                elif system.get('svpIp') == self.rest_host:
                    self.storage_device_id = system.get('storageDeviceId')
                    self.device_model = system.get('model')
                    self.serial_number = system.get('serialNumber')
                    break
            if self.storage_device_id is None:
                LOG.error("Get device id fail,model or something is wrong")
            return succeed
        except Exception as e:
            LOG.error("Get device id error: %s", six.text_type(e))
            raise e

    def get_firmware_version(self):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}'
        result_json = self.get_rest_info(url)
        return None if result_json is None else result_json.get('dkcMicroVersion')

    def get_capacity(self):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/total-capacities/instance'

        return self.get_rest_info(url)

    def get_all_pools(self):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/pools'
        return self.get_rest_info(url)

    def get_volumes(self, head_id,
                    max_number=consts.LDEV_NUMBER_OF_PER_REQUEST):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/ldevs?headLdevId={head_id}&count={max_number}'

        return self.get_rest_info(url)

    def get_system_info(self):
        return self.get_rest_info(RestHandler.COMM_URL, timeout=10)

    def get_controllers(self):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/components/instance'
        return self.get_rest_info(url)

    def get_disks(self):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/drives'
        return self.get_rest_info(url)

    def get_all_ports(self):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/ports'
        return self.get_rest_info(url)

    def get_detail_ports(self, port_id):
        url = f'{RestHandler.COMM_URL}/{self.storage_device_id}/ports/{port_id}'
        return self.get_rest_info(url)
