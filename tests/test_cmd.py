import os
from pathlib import Path
import shlex
import shutil
if os.name != 'nt':
    import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Legacy Linux/Bash integration')
class CmdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.config = self.work / 'commands.conf'
        self.config.write_text('# 示例\nhello -- printf "hello\\n"\npush-test -- printf "push\\n"\n')
        self.env = dict(os.environ, CMD_TOOL_CONFIG=str(self.config))

    def run_cmd(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'xcmd'), *args],
                              env=self.env, cwd=self.work, text=True, capture_output=True)

    def test_execution_prints_command_and_runs(self):
        result = self.run_cmd('hello')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'hello\n')
        self.assertIn('printf "hello\\n"', result.stderr)

    def test_completion_is_prefix_filtered_and_never_executes(self):
        self.config.write_text('push-test -- touch SHOULD_NOT_EXIST\nother -- true\n')
        result = self.run_cmd('--complete', 'p')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'push-test\ttouch SHOULD_NOT_EXIST\n')
        self.assertFalse((self.work / 'SHOULD_NOT_EXIST').exists())

    def test_arguments_are_quoted_and_not_evaluated(self):
        self.config.write_text('args -- printf "<%s>\\n"\n')
        result = self.run_cmd('args', 'two words', '$(touch INJECTED)', '; false', '--flag')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '<two words>\n<$(touch INJECTED)>\n<; false>\n<--flag>\n')
        self.assertFalse((self.work / 'INJECTED').exists())

    def test_pipeline_and_current_directory(self):
        self.config.write_text('where -- pwd\npipe -- printf abc | tr a-z A-Z\n')
        self.assertEqual(self.run_cmd('where').stdout.strip(), str(self.work))
        self.assertEqual(self.run_cmd('pipe').stdout, 'ABC')

    def test_exit_status_is_preserved(self):
        self.config.write_text('fail -- exit 23\n')
        self.assertEqual(self.run_cmd('fail').returncode, 23)

    def test_unknown_name_never_executes(self):
        result = self.run_cmd('missing')
        self.assertEqual(result.returncode, 2)
        self.assertIn('missing', result.stderr)

    def test_invalid_config_is_rejected_before_execution(self):
        for body in ('hello -- touch BAD\nbroken\n',
                     'hello -- touch BAD\nhello -- true\n',
                     'bad/name -- true\n', 'empty -- \n'):
            with self.subTest(body=body):
                self.config.write_text(body)
                result = self.run_cmd('hello')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(str(self.config), result.stderr)
                self.assertFalse((self.work / 'BAD').exists())

    def test_config_reload_bom_crlf_and_delimiter_in_command(self):
        self.config.write_bytes(b'\xef\xbb\xbfhello -- printf "one -- two"\r\n')
        self.assertEqual(self.run_cmd('hello').stdout, 'one -- two')
        self.config.write_text('hello -- printf changed\n')
        self.assertEqual(self.run_cmd('hello').stdout, 'changed')

    def test_missing_config_and_show_list(self):
        result = self.run_cmd('--show', 'hello')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'printf "hello\\n"\n')
        self.assertIn('push-test', self.run_cmd('--list').stdout)
        self.config.unlink()
        result = self.run_cmd('hello')
        self.assertEqual(result.returncode, 2)
        self.assertIn(str(self.config), result.stderr)

    def test_bash_completion_matches_names_and_displays_command(self):
        script = f'''
source {shlex.quote(str(ROOT / 'completion.bash'))}
COMP_WORDS=(xcmd p)
COMP_CWORD=1
_xcmd_tool_complete
printf '\\nREPLY:%s\\n' "${{COMPREPLY[@]}}"
'''
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REPLY:push-test', result.stdout)
        self.assertIn('printf "push\\n"', result.stdout)
        self.assertNotIn('REPLY:hello', result.stdout)

    def test_loading_preserves_unrelated_cmd_function(self):
        script = f'''
xcmd() {{ printf original; }}
source {shlex.quote(str(ROOT / 'completion.bash'))}
printf 'LOAD:%s\\n' "$?"
xcmd
'''
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                                env=self.env, text=True, capture_output=True)
        self.assertIn('LOAD:1', result.stdout)
        self.assertTrue(result.stdout.endswith('original'), result.stdout)
        self.assertIn('xcmd', result.stderr)

    def test_loading_preserves_unrelated_path_executable(self):
        executable = self.work / 'xcmd'
        executable.write_text('#!/bin/sh\nprintf original')
        executable.chmod(0o755)
        script = f'source {shlex.quote(str(ROOT / "completion.bash"))}; xcmd'
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                                env=dict(self.env, PATH=str(self.work) + os.pathsep + self.env['PATH']),
                                text=True, capture_output=True)
        self.assertEqual(result.stdout, 'original')

    def test_loading_twice_preserves_tool_function(self):
        source = f'source {shlex.quote(str(ROOT / "completion.bash"))}'
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                 source + '\n' + source + '\nxcmd --show hello'],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'printf "hello\\n"\n')

    def test_reload_removes_old_tool_function_and_completion(self):
        script = f'''
cmd() {{ python3 "$_CMD_TOOL_BIN" "$@"; }}
_cmd_tool_complete() {{ COMPREPLY=(legacy); }}
complete -F _cmd_tool_complete cmd
source {shlex.quote(str(ROOT / 'completion.bash'))}
declare -F cmd >/dev/null && exit 91
complete -p cmd 2>/dev/null && exit 92
declare -F _cmd_tool_complete >/dev/null && exit 93
xcmd --show hello
'''
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'printf "hello\\n"\n')

    def test_reload_preserves_other_cmd_functions(self):
        script = f'''
cmd() {{ printf original; }}
source {shlex.quote(str(ROOT / 'completion.bash'))}
cmd
'''
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'original')

    def test_real_terminal_tab_displays_and_only_executes_on_enter(self):
        self.config.write_text('push-test -- touch NOT_RUN\npush-other -- printf other\n')
        master, slave = pty.openpty()
        process = subprocess.Popen(['bash', '--noprofile', '--norc', '-i'],
                                   stdin=slave, stdout=slave, stderr=slave,
                                   env=dict(self.env, PS1='CMDTEST> ', TERM='dumb'),
                                   cwd=self.work, start_new_session=True)
        os.close(slave)

        def read_until(marker):
            output = b''
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    output += os.read(master, 65536)
                    if marker in output:
                        while select.select([master], [], [], 0.1)[0]:
                            output += os.read(master, 65536)
                        return output.decode(errors='replace')
            self.fail(f'终端未出现 {marker!r}：{output!r}')

        try:
            read_until(b'CMDTEST> ')
            os.write(master, f'source {shlex.quote(str(ROOT / "completion.bash"))}\n'.encode())
            read_until(b'CMDTEST> ')
            os.write(master, b'xcmd p\t')
            output = read_until(b'printf other\r\n').replace('\x07', '')
            self.assertIn('push-test -- touch NOT_RUN', output)
            self.assertIn('push-other -- printf other', output)
            self.assertIn('CMDTEST> xcmd push-', output)
            self.assertFalse((self.work / 'NOT_RUN').exists())
            os.write(master, b'\x15xcmd push-t\t')
            output = read_until(b'CMDTEST> xcmd push-test ')
            self.assertIn('push-test -- touch NOT_RUN', output)
            self.assertFalse((self.work / 'NOT_RUN').exists())
            os.write(master, b'\n')
            output = read_until(b'CMDTEST> ')
            self.assertIn('+ touch NOT_RUN', output)
            self.assertTrue((self.work / 'NOT_RUN').exists())
            os.write(master, b'exit\n')
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(master)


@unittest.skipUnless(os.name != 'nt', 'Legacy Linux source installer')
class InstallTests(unittest.TestCase):
    def test_upgrade_removes_only_owned_legacy_cmd_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            data = home / '.local/share/cmd-tool'
            data.mkdir(parents=True)
            legacy = data / 'cmd'
            legacy.write_text('old tool executable')
            old_link = home / '.local/bin/cmd'
            old_link.parent.mkdir(parents=True)
            old_link.symlink_to(legacy)
            old_xcmd = home / '.local/bin/xcmd'
            (data / 'xcmd').write_text('previous xcmd executable')
            old_xcmd.symlink_to(data / 'xcmd')
            (home / 'bin').mkdir()
            (home / 'bin/xcmd').symlink_to(data / 'xcmd')
            config = home / '.config/cmd-tool/commands.conf'
            config.parent.mkdir(parents=True)
            config.write_text('mine -- printf preserved\n')
            result = subprocess.run([sys.executable, str(ROOT / 'install.py')],
                                    env=dict(os.environ, HOME=str(home),
                                             XDG_DATA_HOME=str(home / '.local/share'),
                                             XDG_CONFIG_HOME=str(home / '.config')),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(old_link.is_symlink())
            self.assertFalse(old_xcmd.is_symlink())
            self.assertTrue((home / 'bin/xcmd').is_symlink())
            self.assertEqual((home / 'bin/xcmd').resolve(), home / 'bin/cmd-tool/xcmd')
            self.assertEqual(config.read_text(), 'mine -- printf preserved\n')

    def test_upgrade_preserves_unrelated_legacy_cmd_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            old = home / '.local/bin/cmd'
            old.parent.mkdir(parents=True)
            old.write_text('other cmd')
            result = subprocess.run([sys.executable, str(ROOT / 'install.py')],
                                    env=dict(os.environ, HOME=str(home),
                                             XDG_DATA_HOME=str(home / '.local/share'),
                                             XDG_CONFIG_HOME=str(home / '.config')),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(old.read_text(), 'other cmd')
            self.assertTrue((home / 'bin/xcmd').is_symlink())

    def test_install_is_repeatable_and_preserves_user_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / 'user home'
            home.mkdir()
            rc = home / '.bashrc'
            rc.write_text('# user settings\n')
            env = dict(os.environ, HOME=str(home),
                       XDG_DATA_HOME=str(home / '.local/share'),
                       XDG_CONFIG_HOME=str(home / '.config'),
                       PATH=str(home / 'bin') + os.pathsep + os.environ['PATH'])
            env.pop('CMD_TOOL_CONFIG', None)
            for attempt in range(2):
                result = subprocess.run([sys.executable, str(ROOT / 'install.py')],
                                        env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = home / '.config/cmd-tool/commands.conf'
                if attempt == 0:
                    self.assertIn('hello --', config.read_text())
                    config.write_text('mine -- printf installed\n')
            self.assertEqual(config.read_text(), 'mine -- printf installed\n')
            self.assertEqual(rc.read_text().count('# >>> cmd-tool >>>'), 1)
            self.assertIn('# user settings', rc.read_text())
            backups = list(home.glob('.bashrc.cmd-tool.bak.*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), '# user settings\n')
            result = subprocess.run([str(home / 'bin/xcmd'), 'mine'],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'installed')
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                     f'source {shlex.quote(str(rc))}; xcmd --show mine; complete -p xcmd'],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('printf installed', result.stdout)
            self.assertIn('_xcmd_tool_complete xcmd', result.stdout)

    def test_install_does_not_overwrite_an_unrelated_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            executable = home / 'bin/xcmd'
            executable.parent.mkdir(parents=True)
            executable.write_text('unrelated user program')
            result = subprocess.run([sys.executable, str(ROOT / 'install.py')],
                                    env=dict(os.environ, HOME=str(home),
                                             XDG_DATA_HOME=str(home / '.local/share'),
                                             XDG_CONFIG_HOME=str(home / '.config')),
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(executable.read_text(), 'unrelated user program')


if __name__ == '__main__':
    unittest.main()
