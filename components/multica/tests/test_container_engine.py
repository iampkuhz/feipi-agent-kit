"""实际本机 socket 与隔离配置边界；不启动真实容器。"""
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('container_engine', Path(__file__).resolve().parents[1]/'scripts/container_engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class LocalEngine(unittest.TestCase):
    def test_remote_docker_host_is_rejected_without_inspecting_podman(self):
        with patch.dict(os.environ, {'DOCKER_HOST':'ssh://remote.example'}, clear=True), \
                patch.object(engine.subprocess, 'check_output') as inspect:
            with self.assertRaisesRegex(ValueError, '本机 unix'):
                engine.environment()
            inspect.assert_not_called()

    def test_socket_is_derived_from_bound_machine_without_private_shell_environment(self):
        with tempfile.TemporaryDirectory(prefix='multica socket ') as directory:
            home = Path(directory); binding = home/'.config/multica-selfhost/machine.json'
            binding.parent.mkdir(parents=True)
            binding.write_text(json.dumps({'startup':{'podman_machine':'bound-machine'}}))
            path = home/'api.sock'
            with socket.socket(socket.AF_UNIX) as local:
                local.bind(str(path))
                rows = [{'Name':'bound-machine', 'State':'running', 'ConnectionInfo':{'PodmanSocket':{'Path':str(path)}}}]
                with patch.dict(os.environ, {'HOME':str(home),'PATH':'/bin','POSTGRES_PASSWORD':'unrelated','DOCKER_CONTEXT':'remote'}, clear=True), \
                        patch.object(engine.subprocess,'check_output',return_value=json.dumps(rows)) as inspect:
                    environment = engine.environment()
                self.assertEqual(environment['DOCKER_HOST'], 'unix://'+str(path))
                self.assertEqual(set(environment), {'HOME','PATH','DOCKER_HOST'})
                self.assertEqual(inspect.call_args.args[0], ['podman','machine','inspect','bound-machine'])

    def test_regular_file_is_not_accepted_as_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fake.sock'; path.touch()
            with patch.dict(os.environ, {'DOCKER_HOST':'unix://'+str(path)}, clear=True):
                with self.assertRaisesRegex(ValueError, 'socket 不可用'):
                    engine.environment()

    def test_fresh_home_discovers_compose_plugin_without_copying_docker_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); docker = home/'brew/bin/docker'; docker.parent.mkdir(parents=True); docker.touch()
            plugin = home/'brew/lib/docker/cli-plugins/docker-compose'; plugin.parent.mkdir(parents=True); plugin.touch()
            with patch.dict(os.environ, {'HOME':str(home)}, clear=True), patch.object(engine.shutil,'which',return_value=str(docker)):
                config = engine.public_config()
            self.assertEqual(config, {'auths':{}, 'cliPluginsExtraDirs':[str(plugin.parent)]})


if __name__ == '__main__':
    unittest.main()
