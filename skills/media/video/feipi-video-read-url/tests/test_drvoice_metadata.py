"""严道单讲、文章多视频和访问边界的离线回归。"""
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]/'scripts/lib/drvoice_metadata.py'
spec = importlib.util.spec_from_file_location('drvoice_metadata', MODULE)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class DrVoiceMetadataTests(unittest.TestCase):
    manifest = '#EXTM3U\n#EXT-X-TARGETDURATION:60\n#EXTINF:60.000,\nsegment.ts\n#EXT-X-ENDLIST\n'

    def resolve(self, data, url, index='1', evidence=None, manifest=None):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)
            evidence_path=''
            if evidence is not None:
                path=output/'account-evidence.json'
                path.write_text(json.dumps(evidence))
                evidence_path=str(path)
            responses=[io.BytesIO(json.dumps(data).encode())]
            if manifest is not None:
                responses.append(io.BytesIO(manifest.encode()))
            with patch.dict(os.environ, {'AGENT_DRVOICE_VIDEO_INDEX':index,
                                        'AGENT_DRVOICE_ACCOUNT_EVIDENCE':evidence_path}), \
                 patch.object(metadata.urllib.request, 'urlopen', side_effect=responses), \
                 contextlib.redirect_stdout(io.StringIO()):
                metadata.resolve(url,output)
            return json.loads((output/'video_identity.json').read_text()), (output/'.drvoice-media-url').read_text()

    def account_evidence(self, **changes):
        proof=dict(schema='drvoice-account-playback-v1',source_id='drvoice-speaker-123',
                   source_url='https://www.drvoice.cn/v2/speaker/123',
                   checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   login_confirmed=True,playback_reached_end_observed=True,
                   no_registration_or_payment_prompt_seen=True,native_DOM_video_src_observed=True,
                   media_reference_sha256=hashlib.sha256(b'https://video.drvoice.cn/test.m3u8').hexdigest(),
                   manifest_sha256=hashlib.sha256(self.manifest.encode()).hexdigest())
        proof.update(changes)
        return proof

    def registered_hls(self, **changes):
        info=dict(courseInfo=dict(isOpenSign=1,isOpenPayWatch=0),paymentType=0,
                  video=json.dumps([dict(playURL='https://video.drvoice.cn/test.m3u8',duration='60',encrypt=0)]))
        info.update(changes)
        return self.speaker(**info)

    def speaker(self, **extra):
        info=dict(id='123',title='中文单讲',courseInfo={},video=json.dumps([dict(playURL='https://video.drvoice.cn/test.mp4',duration='60',encrypt=0)]))
        info.update(extra)
        return dict(success=True,data=dict(speakerInfo=info))

    def article(self, markup):
        return dict(success=True,data=dict(id='456',title='文章视频',content=markup,createDate='2020-01-01'))

    def test_speaker_identity_unchanged(self):
        identity,media=self.resolve(self.speaker(),'https://www.drvoice.cn/v2/speaker/123')
        self.assertEqual(identity['video_id'],'123')
        self.assertEqual(identity['duration_sec'],60)
        self.assertEqual(media,'https://video.drvoice.cn/test.mp4')

    def test_article_second_video_and_source_child(self):
        data=self.article('<video src="https://videobj.drvoice.cn/one.mp4"></video><video><source src="https://drvoicedev.oss-cn-beijing.aliyuncs.com/two.mp4"></video>')
        identity,media=self.resolve(data,'https://www.drvoice.cn/v2/article/456',index='2')
        self.assertEqual(identity['video_id'],'article-456-video-2')
        self.assertEqual(identity['embedded_video_count'],2)
        self.assertTrue(media.endswith('/two.mp4'))

    def test_legacy_public_asset_uses_tls(self):
        _,media=self.resolve(self.article('<video src="http://drvoice201608.oss-cn-beijing.aliyuncs.com/old.mp4"></video>'),'https://www.drvoice.cn/v2/article/456')
        self.assertTrue(media.startswith('https://'))

    def test_official_legacy_speaker_hosts_and_tls_upgrade(self):
        for source in ['https://videosz.drvoice.cn/lecture.mp4',
                       'http://drvoiceke.oss-cn-beijing.aliyuncs.com/lecture.mp4']:
            with self.subTest(source=source):
                data=self.speaker(video=json.dumps([dict(playURL=source)]))
                _,media=self.resolve(data,'https://www.drvoice.cn/v2/speaker/123')
                self.assertEqual(media,'https://'+source.split('://',1)[1])

    def test_unverified_speaker_host_and_legacy_host_restriction_stop(self):
        for source,course in [('https://videosz.drvoice.cn.example.com/lecture.mp4',{}),
                              ('https://videosz.drvoice.cn/lecture.mp4',dict(isOpenPayWatch=1))]:
            with self.subTest(source=source,course=course),self.assertRaises(ValueError):
                data=self.speaker(courseInfo=course,video=json.dumps([dict(playURL=source)]))
                self.resolve(data,'https://www.drvoice.cn/v2/speaker/123')

    def test_registration_and_encryption_still_stop(self):
        for info in [self.speaker(courseInfo=dict(isOpenSign=1)),self.speaker(video=json.dumps([dict(encrypt=1,playURL='https://video.drvoice.cn/a.mp4')]))]:
            with self.subTest(info=info),self.assertRaises(ValueError):
                self.resolve(info,'https://www.drvoice.cn/v2/speaker/123')

    def test_iframe_foreign_host_and_bad_index_stop(self):
        for markup,index in [('<iframe src="https://mp.weixin.qq.com/player"></iframe>','1'),('<video src="https://example.com/a.mp4"></video>','1'),('<video src="https://video.drvoice.cn/a.mp4"></video>','2')]:
            with self.subTest(markup=markup,index=index),self.assertRaises(ValueError):
                self.resolve(self.article(markup),'https://www.drvoice.cn/v2/article/456',index)

    def test_page_identity_mismatch_stops(self):
        with self.assertRaises(ValueError):
            self.resolve(self.speaker(),'https://www.drvoice.cn/v2/speaker/999')

    def test_single_verified_account_hls_preserves_registration_flag(self):
        identity,media=self.resolve(self.registered_hls(),'https://www.drvoice.cn/v2/speaker/123',
                                    evidence=self.account_evidence(),manifest=self.manifest)
        self.assertEqual(media,'https://video.drvoice.cn/test.m3u8')
        self.assertTrue(identity['account_playback_verified'])
        self.assertEqual(identity['public_watch_flags'],dict(isOpenSign=1,isOpenPayWatch=0))
        self.assertEqual(identity['account_evidence']['manifest_sha256'],hashlib.sha256(self.manifest.encode()).hexdigest())

    def test_account_evidence_is_bound_to_source_and_media(self):
        for change in [dict(schema='allow-all'),dict(source_id='drvoice-speaker-999'),
                       dict(source_url='https://example.com/v2/speaker/123'),
                       dict(source_url='https://www.drvoice.cn/v2/speaker/999'),
                       dict(media_reference_sha256='0'*64),dict(manifest_sha256='not-a-hash')]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.resolve(self.registered_hls(),'https://www.drvoice.cn/v2/speaker/123',
                             evidence=self.account_evidence(**change),manifest=self.manifest)

    def test_incomplete_stale_future_or_naive_account_evidence_stops(self):
        for change in [dict(login_confirmed=False),dict(playback_reached_end_observed=False),
                       dict(no_registration_or_payment_prompt_seen=False),dict(native_DOM_video_src_observed='true'),
                       dict(checked_at='2020-01-01T00:00:00+00:00'),dict(checked_at='2040-01-01T00:00:00+00:00'),
                       dict(checked_at='2026-10-20T12:00:00')]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.resolve(self.registered_hls(),'https://www.drvoice.cn/v2/speaker/123',
                             evidence=self.account_evidence(**change),manifest=self.manifest)

    def test_account_receipt_does_not_allow_paid_or_encrypted_media(self):
        for data in [self.registered_hls(courseInfo=dict(isOpenSign=1,isOpenPayWatch=1)),
                     self.registered_hls(paymentType=1),
                     self.registered_hls(video=json.dumps([dict(playURL='https://video.drvoice.cn/test.m3u8',encrypt=1)]))]:
            with self.subTest(data=data),self.assertRaises(ValueError):
                self.resolve(data,'https://www.drvoice.cn/v2/speaker/123',evidence=self.account_evidence(),manifest=self.manifest)

    def test_account_receipt_does_not_allow_live_keyed_or_changed_hls(self):
        for manifest in [self.manifest.replace('#EXT-X-ENDLIST',''),
                         self.manifest+'#EXT-X-KEY:METHOD=AES-128,URI="key"\n',
                         self.manifest.replace('60.000','59.000')]:
            with self.subTest(manifest=manifest),self.assertRaises(ValueError):
                self.resolve(self.registered_hls(),'https://www.drvoice.cn/v2/speaker/123',
                             evidence=self.account_evidence(),manifest=manifest)

    def test_account_receipt_rejects_article_mp4_and_credential_url(self):
        for data,url in [(self.article('<video src="https://video.drvoice.cn/test.m3u8"></video>'),'https://www.drvoice.cn/v2/article/456'),
                         (self.registered_hls(video=json.dumps([dict(playURL='https://video.drvoice.cn/test.mp4')])),'https://www.drvoice.cn/v2/speaker/123'),
                         (self.registered_hls(video=json.dumps([dict(playURL='https://video.drvoice.cn/test.m3u8?token=private')])),'https://www.drvoice.cn/v2/speaker/123')]:
            with self.subTest(url=url,data=data),self.assertRaises(ValueError):
                self.resolve(data,url,evidence=self.account_evidence(),manifest=self.manifest)


if __name__=='__main__':
    unittest.main()
