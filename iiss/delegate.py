# Copyright 2020 ICON Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse

from iconsdk.exception import JSONRPCException

from run import address_type
from score.chain import ChainScore
from util import die, in_icx, print_response, get_icon_service, get_address_from_keystore, load_keystore


class Delegate(object):

    def __init__(self, service):
        self._chain = ChainScore(service)
        self._icon_service = service

    def query(self, address):
        params = {
            "address": address
        }
        return self._chain.call("getDelegation", params)

    def get_prep(self, address):
        params = {
            "address": address
        }
        return self._chain.call("getPRep", params)

    def set(self, wallet, delegations):
        delegation_list = []
        for address, value in delegations.items():
            if int(value, 16) > 0:
                delegation_list.append({"address": address, "value": value})
        params = {
            "delegations": delegation_list
        }
        return self._chain.invoke(wallet, "setDelegation", params)

    def get_total_delegated(self, address):
        result = self.query(address)
        return int(result['totalDelegated'], 16)

    def ask_to_set(self, result, keystore, passwd):
        confirm = input('\n==> Are you sure you want to set new delegations? (y/n) ')
        if confirm == 'y':
            delegations = self._get_new_delegations(result)
            wallet = load_keystore(keystore, passwd)
            tx_hash = self.set(wallet, delegations)
            print(f'\n==> Success: https://tracker.icon.foundation/transaction/{tx_hash}')

    def _get_new_delegations(self, result):
        delegations = self.convert_to_map(result['delegations'])
        voting_power = int(result['votingPower'], 16)
        self.print_delegations(delegations, voting_power)
        while True:
            try:
                confirm = input('\n==> The address you want to set (\'q\' for finish): ')
                if confirm == 'q':
                    return delegations
                address = address_type(confirm)
                self.print_prep_info(address)
                maximum = voting_power + int(delegations.get(address, '0x0'), 16)
                amount = self._check_value(input(f'Delegation amount (max: {maximum}): '), maximum)
                delegations[address] = hex(amount)
                voting_power = maximum - amount
                self.print_delegations(delegations, voting_power)
            except KeyboardInterrupt:
                die('exit')
            except argparse.ArgumentTypeError:
                print('Error: invalid address')
                continue
            except ValueError as e:
                print(e.__str__())
                continue
            except JSONRPCException:
                continue

    @staticmethod
    def convert_to_map(delegation_list):
        delegations = {}
        for delegation in delegation_list:
            address = delegation["address"]
            value = delegation["value"]
            delegations[address] = value
        return delegations

    @staticmethod
    def _check_value(value: str, maximum: int):
        try:
            amount = int(value)
            if 0 <= amount <= maximum:
                return amount
            raise ValueError(f'Error: value should be 0 <= (value) <= {maximum}')
        except ValueError:
            raise ValueError(f'Error: value should be integer')

    @staticmethod
    def print_delegations(delegations, voting_power, header='delegations'):
        print()
        print_response(header, delegations)
        print('Remaining votingPower =', voting_power)

    @staticmethod
    def print_status(address, result):
        print('[Delegation]')
        print_response(address, result)
        print('DelegatedICX =', in_icx(int(result['totalDelegated'], 16)))

    def print_prep_info(self, prep_addr):
        print_response('P-Rep Info', self.get_prep(prep_addr))


def run(args):
    icon_service = get_icon_service(args.endpoint)
    delegate = Delegate(icon_service)
    if args.prep:
        try:
            delegate.print_prep_info(args.prep)
        except JSONRPCException:
            pass
        exit(-1)
    if args.keystore:
        address = get_address_from_keystore(args.keystore)
    elif args.address:
        address = args.address
    else:
        die('Error: keystore or address should be specified')
    result = delegate.query(address)
    delegate.print_status(address, result)
    if args.set:
        if not args.keystore:
            die('Error: keystore should be specified to set delegations')
        delegate.ask_to_set(result, args.keystore, args.password)
