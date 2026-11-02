# Flow map — area `main`

Files covered: `tools/gen_site.py`, `tools/prune_release.py`, `tools/verify_apk.py`, `tools/release_check.py`, `tools/apk_package.py`, `src/scripts/matrix.py`, `src/core/patcher.py`, `src/core/builder.py`. Tests: `tests/test_release_flow.py`. Run: `python3 tools/flow/flowmap.py check`.

## Paths

One row per path, one test per row. The test's name or text holds the ID. "If it fails" is the first thing to check.

| ID | Entry | Conditions | Expected | Checks | If it fails |
|---|---|---|---|---|---|
| P-REL-01 | tools/gen_site.py collect/superseded/build_version | same day rebuild offers the highest version | as named | `test_P_REL_01_same_day_rebuild_offers_the_highest_version` | gen_site.py collect, superseded |
| P-REL-02 | tools/gen_site.py collect/superseded/build_version | a newer release wins over an older one | as named | `test_P_REL_02_a_newer_release_wins_over_an_older_one` | gen_site.py collect, superseded |
| P-REL-03 | tools/gen_site.py collect/superseded/build_version | a pin wins over a higher version | as named | `test_P_REL_03_a_pin_wins_over_a_higher_version` | gen_site.py collect, superseded |
| P-REL-04 | tools/gen_site.py collect/superseded/build_version | update version uses the apps own bundle | as named | `test_P_REL_04_update_version_uses_the_apps_own_bundle` | gen_site.py collect, superseded |
| P-REL-05 | tools/gen_site.py collect/superseded/build_version | update versions keep their order | as named | `test_P_REL_05_update_versions_keep_their_order` | gen_site.py collect, superseded |
| P-REL-06 | tools/gen_site.py collect/superseded/build_version | no bundle in the notes ranks lowest | as named | `test_P_REL_06_no_bundle_in_the_notes_ranks_lowest` | gen_site.py collect, superseded |
| P-REL-07 | tools/gen_site.py collect/superseded/build_version | an incomplete replacement replaces nothing | as named | `test_P_REL_07_an_incomplete_replacement_replaces_nothing` | gen_site.py collect, superseded |
| P-REL-08 | tools/gen_site.py collect/superseded/build_version | api reads retry a cut off answer only | as named | `test_P_REL_08_api_reads_retry_a_cut_off_answer_only` | gen_site.py collect, superseded |
| P-REL-09 | Site workflow: prune_release.py | removed once the live site stopped offering it | as named | `test_P_REL_09_removed_once_the_live_site_stopped_offering_it` | prune_release.py |
| P-REL-10 | Site workflow: prune_release.py | kept while the live site still offers it | as named | `test_P_REL_10_kept_while_the_live_site_still_offers_it` | prune_release.py |
| P-REL-11 | Site workflow: prune_release.py | waits for pages to deploy | as named | `test_P_REL_11_waits_for_pages_to_deploy` | prune_release.py |
| P-REL-12 | Site workflow: prune_release.py | nothing superseded touches nothing | as named | `test_P_REL_12_nothing_superseded_touches_nothing` | prune_release.py |
| P-REL-13 | Site workflow: prune_release.py | an apk the new notes would mislabel goes | as named | `test_P_REL_13_an_apk_the_new_notes_would_mislabel_goes` | prune_release.py |
| P-REL-14 | Site workflow: prune_release.py | the build job entry point deletes them | as named | `test_P_REL_14_the_build_job_entry_point_deletes_them` | prune_release.py |
| P-REL-15 | Site workflow: prune_release.py | delete and live urls use the real endpoints | as named | `test_P_REL_15_delete_and_live_urls_use_the_real_endpoints` | prune_release.py |
| P-REL-16 | Build APKs: verify_apk.py | a good apk passes | as named | `test_P_REL_16_a_good_apk_passes` | verify_apk.py problems |
| P-REL-17 | Build APKs: verify_apk.py | the version inside must match the file name | as named | `test_P_REL_17_the_version_inside_must_match_the_file_name` | verify_apk.py problems |
| P-REL-18 | Build APKs: verify_apk.py | the libraries must be for the named cpu | as named | `test_P_REL_18_the_libraries_must_be_for_the_named_cpu` | verify_apk.py problems |
| P-REL-19 | Build APKs: verify_apk.py | the patch must be in the app | as named | `test_P_REL_19_the_patch_must_be_in_the_app` | verify_apk.py problems |
| P-REL-20 | Build APKs: verify_apk.py | the wrong key is refused | as named | `test_P_REL_20_the_wrong_key_is_refused` | verify_apk.py problems |
| P-REL-21 | Build APKs: verify_apk.py | the package must be the configured clone | as named | `test_P_REL_21_the_package_must_be_the_configured_clone` | verify_apk.py problems |
| P-REL-22 | Build APKs: verify_apk.py | junk never passes | as named | `test_P_REL_22_junk_never_passes` | verify_apk.py problems |
| P-REL-23 | Build APKs: verify_apk.py | a rejected apk is deleted and the job fails | as named | `test_P_REL_23_a_rejected_apk_is_deleted_and_the_job_fails` | verify_apk.py problems |
| P-REL-24 | Build APKs: verify_apk.py | nothing left means no notes for this job | as named | `test_P_REL_24_nothing_left_means_no_notes_for_this_job` | verify_apk.py problems |
| P-REL-25 | Build APKs: verify_apk.py | ci without the expected key fails | as named | `test_P_REL_25_ci_without_the_expected_key_fails` | verify_apk.py problems |
| P-REL-26 | Build APKs: verify_apk.py | config gives each clone and its patches | as named | `test_P_REL_26_config_gives_each_clone_and_its_patches` | verify_apk.py problems |
| P-REL-27 | Build APKs: verify_apk.py | the manifest reader gives the attributes | as named | `test_P_REL_27_the_manifest_reader_gives_the_attributes` | verify_apk.py problems |
| P-REL-28 | CI: matrix.py check_builds_needed | an app left on old patches is behind | as named | `test_P_REL_28_an_app_left_on_old_patches_is_behind` | matrix.py check_builds_needed, _apps_behind |
| P-REL-29 | CI: matrix.py check_builds_needed | two bundles after a straddled build count as behind | as named | `test_P_REL_29_two_bundles_after_a_straddled_build_count_as_behind` | matrix.py check_builds_needed, _apps_behind |
| P-REL-30 | CI: matrix.py check_builds_needed | a lower version build is retried | as named | `test_P_REL_30_a_lower_version_build_is_retried` | matrix.py check_builds_needed, _apps_behind |
| P-REL-31 | CI: matrix.py check_builds_needed | an app never built is behind | as named | `test_P_REL_31_an_app_never_built_is_behind` | matrix.py check_builds_needed, _apps_behind |
| P-REL-32 | CI: matrix.py check_builds_needed | a keyword app is left to its keywords | as named | `test_P_REL_32_a_keyword_app_is_left_to_its_keywords` | matrix.py check_builds_needed, _apps_behind |
| P-REL-33 | CI: matrix.py check_builds_needed | nothing new builds nothing | as named | `test_P_REL_33_nothing_new_builds_nothing` | matrix.py check_builds_needed, _apps_behind |
| P-REL-34 | CI: matrix.py check_builds_needed | a new patch release builds | as named | `test_P_REL_34_a_new_patch_release_builds` | matrix.py check_builds_needed, _apps_behind |
| P-REL-35 | CI: matrix.py check_builds_needed | a new stremio version builds | as named | `test_P_REL_35_a_new_stremio_version_builds` | matrix.py check_builds_needed, _apps_behind |
| P-REL-36 | CI: matrix.py check_builds_needed | a failed app is retried at most once a day | as named | `test_P_REL_36_a_failed_app_is_retried_at_most_once_a_day` | matrix.py check_builds_needed, _apps_behind |
| P-REL-37 | CI: matrix.py check_builds_needed | a failed comparison starts nothing | as named | `test_P_REL_37_a_failed_comparison_starts_nothing` | matrix.py check_builds_needed, _apps_behind |
| P-REL-38 | CI: matrix.py check_builds_needed | our newest release is found in any list order | as named | `test_P_REL_38_our_newest_release_is_found_in_any_list_order` | matrix.py check_builds_needed, _apps_behind |
| P-REL-39 | CI: matrix.py check_builds_needed | expected bundle is what a build would use | as named | `test_P_REL_39_expected_bundle_is_what_a_build_would_use` | matrix.py check_builds_needed, _apps_behind |
| P-REL-40 | CI: matrix.py check_builds_needed | prerelease labels keep their order | as named | `test_P_REL_40_prerelease_labels_keep_their_order` | matrix.py check_builds_needed, _apps_behind |
| P-REL-41 | builder -> patcher.py | a named patch that did not apply fails the build | as named | `test_P_REL_41_a_named_patch_that_did_not_apply_fails_the_build` | patcher.py patch, older_supported_versions |
| P-REL-42 | builder -> patcher.py | older versions come highest first | as named | `test_P_REL_42_older_versions_come_highest_first` | patcher.py patch, older_supported_versions |
| P-REL-43 | builder._build_single | the next version down is built and marked | as named | `test_P_REL_43_the_next_version_down_is_built_and_marked` | builder.py _build_single, _last_shipped |
| P-REL-44 | builder._build_single | never below what phones already have | as named | `test_P_REL_44_never_below_what_phones_already_have` | builder.py _build_single, _last_shipped |
| P-REL-45 | builder._build_single | a named version does not fall back | as named | `test_P_REL_45_a_named_version_does_not_fall_back` | builder.py _build_single, _last_shipped |
| P-REL-46 | builder._build_single | a working top version has no mark | as named | `test_P_REL_46_a_working_top_version_has_no_mark` | builder.py _build_single, _last_shipped |
| P-REL-47 | builder._build_single | last shipped reads the newest build of this app | as named | `test_P_REL_47_last_shipped_reads_the_newest_build_of_this_app` | builder.py _build_single, _last_shipped |
| P-REL-48 | Health workflow: release_check.py | a healthy world has no problems | as named | `test_P_REL_48_a_healthy_world_has_no_problems` | release_check.py |
| P-REL-49 | Health workflow: release_check.py | the bug that started this is caught | as named | `test_P_REL_49_the_bug_that_started_this_is_caught` | release_check.py |
| P-REL-50 | Health workflow: release_check.py | a missing app is caught | as named | `test_P_REL_50_a_missing_app_is_caught` | release_check.py |
| P-REL-51 | Health workflow: release_check.py | a wrong update page is caught | as named | `test_P_REL_51_a_wrong_update_page_is_caught` | release_check.py |
| P-REL-52 | Health workflow: release_check.py | an apk that is not what is promised is caught | as named | `test_P_REL_52_an_apk_that_is_not_what_is_promised_is_caught` | release_check.py |
| P-REL-53 | Health workflow: release_check.py | release notes with no bundle are caught | as named | `test_P_REL_53_release_notes_with_no_bundle_are_caught` | release_check.py |
| P-REL-54 | Health workflow: release_check.py | upstream ahead of the offer is caught | as named | `test_P_REL_54_upstream_ahead_of_the_offer_is_caught` | release_check.py |
| P-REL-55 | Health workflow: release_check.py | the runs are checked | as named | `test_P_REL_55_the_runs_are_checked` | release_check.py |
| P-REL-56 | Health workflow: release_check.py | conflicts and unknown packages are caught | as named | `test_P_REL_56_conflicts_and_unknown_packages_are_caught` | release_check.py |
| P-REL-57 | Health workflow: release_check.py | a problem counts only after its grace | as named | `test_P_REL_57_a_problem_counts_only_after_its_grace` | release_check.py |
| P-REL-61 | Health workflow: release_check.py | healthy run is green and quiet | as named | `test_P_REL_61_healthy_run_is_green_and_quiet` | release_check.py |
| P-REL-62 | Health workflow: release_check.py | a problem turns the run red and alerts | as named | `test_P_REL_62_a_problem_turns_the_run_red_and_alerts` | release_check.py |
| P-REL-63 | Health workflow: release_check.py | a problem in its grace waits green | as named | `test_P_REL_63_a_problem_in_its_grace_waits_green` | release_check.py |
| P-REL-64 | Health workflow: release_check.py | unreadable releases judge nothing else | as named | `test_P_REL_64_unreadable_releases_judge_nothing_else` | release_check.py |
| P-REL-65 | Health workflow: release_check.py | a running build skips the check | as named | `test_P_REL_65_a_running_build_skips_the_check` | release_check.py |
| P-REL-67 | Health workflow: release_check.py | gather reads every source | as named | `test_P_REL_67_gather_reads_every_source` | release_check.py |
| P-REL-68 | Health workflow: release_check.py | a source that cannot be read is its own problem | as named | `test_P_REL_68_a_source_that_cannot_be_read_is_its_own_problem` | release_check.py |
| P-REL-69 | Health workflow: release_check.py | feed and bundles are read as a build would | as named | `test_P_REL_69_feed_and_bundles_are_read_as_a_build_would` | release_check.py |
| P-REL-70 | Health workflow: release_check.py | flow test failures are read from its log | as named | `test_P_REL_70_flow_test_failures_are_read_from_its_log` | release_check.py |
| P-REL-71 | Health workflow: release_check.py | read apk turns any failure into a finding | as named | `test_P_REL_71_read_apk_turns_any_failure_into_a_finding` | release_check.py |
| P-REL-72 | Health workflow: release_check.py | config gives the enabled apps | as named | `test_P_REL_72_config_gives_the_enabled_apps` | release_check.py |
| P-REL-73 | releases -> gen_site.main -> check_offers | same day rebuild end to end | as named | `test_P_REL_73_same_day_rebuild_end_to_end` | gen_site.py main, then release_check.py |
| P-REL-74 | releases -> gen_site.main -> check_offers | a wrong key publishes nothing | as named | `test_P_REL_74_a_wrong_key_publishes_nothing` | gen_site.py main, then release_check.py |
| P-REL-75 | releases -> gen_site.main -> check_offers | a running build publishes nothing | as named | `test_P_REL_75_a_running_build_publishes_nothing` | gen_site.py main, then release_check.py |
| P-REL-76 | apk_package.py over HTTP or a file | package and signer over http | as named | `test_P_REL_76_package_and_signer_over_http` | apk_package.py |
| P-REL-77 | apk_package.py over HTTP or a file | a local file reads the same | as named | `test_P_REL_77_a_local_file_reads_the_same` | apk_package.py |
| P-REL-78 | apk_package.py over HTTP or a file | an unsigned or broken file is refused | as named | `test_P_REL_78_an_unsigned_or_broken_file_is_refused` | apk_package.py |
| P-REL-79 | apk_package.py over HTTP or a file | utf16 string pools read too | as named | `test_P_REL_79_utf16_string_pools_read_too` | apk_package.py |
| P-REL-80 | apk_package.py over HTTP or a file | the command line prints the answer | as named | `test_P_REL_80_the_command_line_prints_the_answer` | apk_package.py |
| P-REL-81 | matrix.py get_matrix, check_builds_needed | each app of the brand is listed | as named | `test_P_REL_81_each_app_of_the_brand_is_listed` | matrix.py |
| P-REL-82 | matrix.py get_matrix, check_builds_needed | a dev brand is a prerelease | as named | `test_P_REL_82_a_dev_brand_is_a_prerelease` | matrix.py |
| P-REL-83 | matrix.py get_matrix, check_builds_needed | an unknown source stops the build | as named | `test_P_REL_83_an_unknown_source_stops_the_build` | matrix.py |
| P-REL-84 | matrix.py get_matrix, check_builds_needed | keywords filter only with the filter on | as named | `test_P_REL_84_keywords_filter_only_with_the_filter_on` | matrix.py |
| P-REL-85 | matrix.py get_matrix, check_builds_needed | force builds every brand and no apps builds none | as named | `test_P_REL_85_force_builds_every_brand_and_no_apps_builds_none` | matrix.py |
| P-REL-86 | matrix.py get_matrix, check_builds_needed | an unreadable upstream builds rather than misses | as named | `test_P_REL_86_an_unreadable_upstream_builds_rather_than_misses` | matrix.py |
| P-REL-87 | matrix.py get_matrix, check_builds_needed | a removed patch repo skips that brand | as named | `test_P_REL_87_a_removed_patch_repo_skips_that_brand` | matrix.py |
| P-REL-88 | matrix.py get_matrix, check_builds_needed | a brand with no release yet builds | as named | `test_P_REL_88_a_brand_with_no_release_yet_builds` | matrix.py |
| P-REL-89 | matrix.py get_matrix, check_builds_needed | feed failures | as named | `test_P_REL_89_feed_failures` | matrix.py |
| P-REL-90 | matrix.py get_matrix, check_builds_needed | the newest dev release is found by date | as named | `test_P_REL_90_the_newest_dev_release_is_found_by_date` | matrix.py |
| P-REL-91 | matrix.py get_matrix, check_builds_needed | the command line runs the right check | as named | `test_P_REL_91_the_command_line_runs_the_right_check` | matrix.py |
| P-REL-92 | tools/gen_site.py collect | an apk still uploading is not offered | as named | `test_P_REL_92_an_apk_still_uploading_is_not_offered` | gen_site.py collect |
| P-REL-93 | tools/gen_site.py collect | architectures are ordered by version | as named | `test_P_REL_93_architectures_are_ordered_by_version` | gen_site.py collect |
| P-REL-94 | sig.txt against config.toml | every enabled app has a stock signature to check | as named | `test_P_REL_94_every_enabled_app_has_a_stock_signature_to_check` | sig.txt |

## Mode combinations

Not exercised by these tests, and proven by a real run instead: the bash steps of the workflows, GitHub's scheduler, and Pages itself. tools/release_check.py watches their results from outside every six hours.

Which switches and settings change these paths, and which combinations are exercised.

## Not exercised — justified

Written by `flowmap.py justify FILE:LINE CLASS "REASON"`. The anchor is the hash of that line's code: moving the line is fine,
changing its code fails the gate until the row is reviewed. Classes: `unreachable` (give the proof), `defensive` (what would have
to fail), `external` (where it IS exercised), `presentation` (only looks change). "Hard to test" is not a reason: write the test.

| Location | Anchor | Class | Reason |
|---|---|---|---|
