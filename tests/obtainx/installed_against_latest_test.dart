// morphe-builder: ObtainX's own decision for installed against latest, real settings from our links, real versions.
// Not run by our CI: copy into ObtainX's test/ folder and run `flutter test` there. warning=true is 'Version order unclear'.
import 'package:flutter_test/flutter_test.dart';
import 'package:obtainium/pages/app.dart';
import 'package:obtainium/providers/apps_provider_updates.dart';
import 'package:obtainium/providers/source_provider.dart';
import 'package:obtainium/version/app_version.dart';

App app(String id, String installed, String latest) => App(
  id: id, url: 'https://qutaiba-khader.github.io/morphe-builder/obtainium/$id.html',
  author: 'Qutaiba-Khader', name: id, installedVersion: installed, latestVersion: latest,
  preferredApkIndex: 0, apkUrls: [MapEntry('$id-v1-all.apk', 'https://github.com/x/$id-v1-all.apk')],
  additionalSettings: {'versionDetection': true, 'versionExtractionRegEx': 'name="build-version" content="([^"]+)"',
    'matchGroupToUse': '1', 'versionExtractWholePage': true, 'apkFilterRegEx': r'\.apk$'});

void main() {
  const cases = [
    // the owner's screen: TikTok before the fix
    ['BEFORE tiktok', '46.2.3', '46.2.3-0.8.1'],
    ['BEFORE stremio-phone', '2.5.1', '2.5.1-0.6.0'],
    // every app, current, as live now: the page offers the APK's versionName
    ['current tiktok', '46.2.3', '46.2.3'],
    ['current reddit', '2026.40.0', '2026.40.0'],
    ['current youtube', '21.30.216', '21.30.216'],
    ['current reddit-exp', '2026.42.0', '2026.42.0'],
    ['current youtube-exp', '21.44.528', '21.44.528'],
    ['current stremio-phone', '2.5.1', '2.5.1'],
    ['current stremio-tv', '1.12.1', '1.12.1'],
    // an older app on the phone
    ['older app', '21.20.405', '21.30.216'],
    // installed before the change, a new build carrying the patch number
    ['next build tiktok', '46.2.3', '46.2.3.0.8.2'],
    ['next build stremio', '2.5.1', '2.5.1.0.6.1'],
    ['next build youtube-exp', '21.44.528', '21.44.528.2.1.0.7'],
    // after that: installed = the build's own name
    ['current dotted', '46.2.3.0.8.2', '46.2.3.0.8.2'],
    ['patch-only update', '46.2.3.0.8.2', '46.2.3.0.9.0'],
    ['new app version', '46.2.3.0.9.0', '46.2.4.0.9.0'],
    ['dev update', '21.44.528.2.1.0.6', '21.44.528.2.1.0.7'],
    ['patch lower than phone', '46.2.3.0.9.0', '46.2.3.0.8.2'],
    // our own fix on the same bundle, then the next bundle
    ['rebuild youtube', '21.30.216.2.0.0', '21.30.216.2.0.0.1'],
    ['rebuild reddit', '2026.40.0.2.0.0', '2026.40.0.2.0.0.1'],
    ['rebuild current', '21.30.216.2.0.0.1', '21.30.216.2.0.0.1'],
    ['bundle after rebuild', '21.30.216.2.0.0.1', '21.30.216.2.0.1'],
    ['app after rebuild', '21.30.216.2.0.0.1', '21.33.100.2.0.0'],
  ];
  test('verdicts', () {
    for (final c in cases) {
      final a = app('com.example.x', c[1], c[2]);
      final d = versionDecisionForApp(a);
      print('${c[0].padRight(24)} ${c[1].padRight(20)} ${c[2].padRight(20)} ${d.relation.name.padRight(8)} ${appVersionVerdictForDisplay(a).name.padRight(16)} warning=${versionOrderUncertainUpdate(a)} update=${appHasActionableUpdate(a)}');
    }
  });
}
