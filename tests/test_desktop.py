from pathlib import Path

import pytest

from babblet.desktop import (DesktopServices, resolve_microphone,load_preferences,
    save_preferences,service_commands,changed_services)


def test_microphone_follows_saved_name_and_host_api_when_indices_change():
    devices=[{'name':'Other','max_input_channels':1,'hostapi':0},
             {'name':'Saved mic','max_input_channels':1,'hostapi':1},
             {'name':'Saved mic','max_input_channels':1,'hostapi':0}]
    assert resolve_microphone(devices,{'microphone_name':'Saved mic','microphone_hostapi':0})==2
    with pytest.raises(RuntimeError,match='microphone'):
        resolve_microphone(devices,{'microphone_name':'Unplugged'})


def test_existing_healthy_service_is_reused_without_starting_another_process(tmp_path,monkeypatch):
    services=DesktopServices(tmp_path)
    monkeypatch.setattr(services,'get_json',lambda *args,**kwargs:{'ready':True})
    monkeypatch.setattr(services,'launch',lambda *args:pytest.fail('must reuse existing service'))
    services.ensure('test',['unused'],'http://127.0.0.1:8090/healthz',lambda data:data.get('ready'))


def test_busy_port_is_not_given_a_duplicate_process(tmp_path,monkeypatch):
    services=DesktopServices(tmp_path)
    monkeypatch.setattr(services,'get_json',lambda *args,**kwargs:None)
    monkeypatch.setattr(services,'listening',lambda url:True)
    monkeypatch.setattr(services,'launch',lambda *args:pytest.fail('occupied port must not start another model'))
    with pytest.raises(RuntimeError,match='already in use'):
        services.ensure('test',['unused'],'http://127.0.0.1:8090/healthz',lambda data:False)


def test_service_exit_is_reported_instead_of_claiming_ready(tmp_path,monkeypatch):
    services=DesktopServices(tmp_path)
    monkeypatch.setattr(services,'get_json',lambda *args,**kwargs:None)
    monkeypatch.setattr(services,'listening',lambda url:False)
    monkeypatch.setattr(services,'launch',lambda *args:type('Exited',(),{'poll':lambda self:1})())
    with pytest.raises(RuntimeError,match='could not start'):
        services.ensure('test',['unused'],'http://127.0.0.1:8090/healthz',lambda data:False)


def model_root(root):
    (root/'models/whisper-turbo').mkdir(parents=True)
    (root/'models/whisper-turbo/model.bin').touch()
    (root/'models/whisper-hebrew').mkdir()
    (root/'models/whisper-hebrew/model.bin').touch()
    (root/'models/hymt2').mkdir()
    for quant in ('Q8_0','Q4_K_M'): (root/f'models/hymt2/Hy-MT2-1.8B-{quant}.gguf').touch()
    return root


def test_preferences_validate_and_roundtrip_without_overwriting_good_settings(tmp_path):
    model_root(tmp_path)
    preferences={**load_preferences(tmp_path),'translation_model':'q4','speech_device':'cpu','debug_audio':False}
    save_preferences(tmp_path,preferences)
    assert load_preferences(tmp_path)==preferences
    for bad in [{'translation_model':'unknown'},{'speech_device':'invalid'},{'debug_audio':'false'},
                {'speech_model':'../other'},{'hebrew_timeout':0}]:
        with pytest.raises(ValueError): save_preferences(tmp_path,{**preferences,**bad})
        assert load_preferences(tmp_path)==preferences


def test_preferences_drive_real_service_arguments_including_microphone_and_disabled_features(tmp_path):
    model_root(tmp_path)
    settings={**load_preferences(tmp_path),'microphone_name':'USB mic','microphone_hostapi':1,
        'translation_model':'q4','translation_device':'cpu','speech_device':'cpu',
        'hebrew_enabled':False,'debug_audio':False,'max_job_age':30}
    commands=service_commands(tmp_path,settings,[{'name':'USB mic','hostapi':1,'max_input_channels':1}])
    speech=list(map(str,commands['display']));translation=list(map(str,commands['translation']))
    assert speech[speech.index('--audio-device')+1]=='0'
    assert speech[speech.index('--device')+1]=='cpu'
    assert '--no-hebrew-second' in speech and '--debug-audio' not in speech
    assert speech[speech.index('--max-job-age')+1]=='30'
    assert translation[translation.index('-ngl')+1]=='0'
    assert translation[translation.index('-m')+1].endswith('Hy-MT2-1.8B-Q4_K_M.gguf')


def test_only_affected_services_restart_for_preference_changes(tmp_path):
    before=load_preferences(tmp_path)
    assert changed_services(before,{**before,'microphone_name':'New mic'})==['display']
    assert changed_services(before,{**before,'translation_model':'q4'})==['display','translation']
    assert changed_services(before,{**before,'open_browser':False})==[]


def test_restart_refuses_a_reused_pid_belonging_to_an_unrelated_program(tmp_path,monkeypatch):
    directory=tmp_path/'artifacts';directory.mkdir();(directory/'display.pid').write_text('123')
    services=DesktopServices(tmp_path)
    monkeypatch.setattr(services,'process_info',lambda pid:{'ExecutablePath':'C:/unrelated.exe','CommandLine':'other'})
    with pytest.raises(RuntimeError,match='safely'):
        services.stop_service('display')


def test_restart_recovers_stale_pid_from_port_only_when_executable_belongs_to_this_workspace(tmp_path,monkeypatch):
    from types import SimpleNamespace
    directory=tmp_path/'artifacts';directory.mkdir();(directory/'translation.pid').write_text('123')
    services=DesktopServices(tmp_path);calls=[]
    monkeypatch.setattr(services,'process_info',lambda pid:None if pid==123 else {
        'ExecutablePath':str(tmp_path/'runtime/llama/llama-server.exe'),'CommandLine':'llama-server'})
    monkeypatch.setattr(services,'port_owner',lambda url:456)
    monkeypatch.setattr(services,'listening',lambda url:not calls)
    monkeypatch.setattr('babblet.desktop.subprocess.run',lambda command,**kwargs:calls.append(command) or SimpleNamespace(returncode=0))
    services.stop_service('translation')
    assert calls==[['taskkill','/PID','456','/T','/F']]
