# Flow map — area `main`

Files covered: `tools/gen_site.py`, `tools/prune_release.py`, `tools/verify_apk.py`, `tools/release_check.py`, `tools/apk_package.py`, `src/scripts/matrix.py`, `src/core/patcher.py`, `src/core/builder.py`. Tests: `tests/test_release_flow.py`, `tests/test_version_history.py` (real formats: `version-formats.md`). Run: `python3 tools/flow/flowmap.py check`.

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
| P-REL-13 | release flow | a rebuild keeps the lines of apks it did not rebuild | as named | `test_P_REL_13_a_rebuild_keeps_the_lines_of_apks_it_did_not_rebuild` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-14 | Build APKs: prune_release.py --merge-notes | the build job entry point writes the merged notes | as named | `test_P_REL_14_the_build_job_entry_point_writes_the_merged_notes` | prune_release.py, build.yml |
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
| P-REL-100 | build.yml | nothing uploads before the check | as named | `test_P_REL_100_nothing_uploads_before_the_check` | build.yml |
| P-REL-101 | build.yml | a rebuild never drafts a published release | as named | `test_P_REL_101_a_rebuild_never_drafts_a_published_release` | build.yml |
| P-REL-102 | ci.yml | a crashed check cannot look like nothing new | as named | `test_P_REL_102_a_crashed_check_cannot_look_like_nothing_new` | ci.yml |
| P-REL-103 | site.yml, health.yml | the site prunes after publishing and health keeps its state | as named | `test_P_REL_103_the_site_prunes_after_publishing_and_health_keeps_its_state` | site.yml, health.yml |
| P-REL-104 | apk_package.py names_from_url | file names are read over http | as named | `test_P_REL_104_file_names_are_read_over_http` | apk_package.py |
| P-REL-105 | release_check.py _text | live pages are read with retries | as named | `test_P_REL_105_live_pages_are_read_with_retries` | release_check.py |
| P-REL-106 | verify_apk.py main | no apks leaves no mark | as named | `test_P_REL_106_no_apks_leaves_no_mark` | verify_apk.py |
| P-REL-107 | release flow, review findings | a straddled build is labelled with the lower bundle | as named | `test_P_REL_107_a_straddled_build_is_labelled_with_the_lower_bundle` | gen_site.py, release_check.py, builder.py |
| P-REL-108 | release flow, review findings | a pin wins over a newer release and a missing pin is reported | as named | `test_P_REL_108_a_pin_wins_over_a_newer_release_and_a_missing_pin_is_reported` | gen_site.py, release_check.py, builder.py |
| P-REL-109 | release flow, review findings | a final version beats its beta | as named | `test_P_REL_109_a_final_version_beats_its_beta` | gen_site.py, release_check.py, builder.py |
| P-REL-110 | release flow, review findings | what was shipped reads past a hyphenated cpu name | as named | `test_P_REL_110_what_was_shipped_reads_past_a_hyphenated_cpu_name` | gen_site.py, release_check.py, builder.py |
| P-REL-111 | release flow, review findings | a patch only rebuild the site missed is stale | as named | `test_P_REL_111_a_patch_only_rebuild_the_site_missed_is_stale` | gen_site.py, release_check.py, builder.py |
| P-REL-112 | release flow, review findings | notes without its own bundle are reported | as named | `test_P_REL_112_notes_without_its_own_bundle_are_reported` | gen_site.py, release_check.py, builder.py |
| P-REL-113 | release flow, review findings | a tiny asset is not offered | as named | `test_P_REL_113_a_tiny_asset_is_not_offered` | gen_site.py, release_check.py, builder.py |
| P-REL-123 | readers | a release with other files still gives the bundle | as named | `test_P_REL_123_a_release_with_other_files_still_gives_the_bundle` | matrix.py, apk_package.py, gen_site.py, verify_apk.py |
| P-REL-124 | readers | a typed attribute that is no integer is skipped | as named | `test_P_REL_124_a_typed_attribute_that_is_no_integer_is_skipped` | matrix.py, apk_package.py, gen_site.py, verify_apk.py |
| P-REL-125 | readers | releases are read page by page | as named | `test_P_REL_125_releases_are_read_page_by_page` | matrix.py, apk_package.py, gen_site.py, verify_apk.py |
| P-REL-126 | readers | a pinned table is recognised | as named | `test_P_REL_126_a_pinned_table_is_recognised` | matrix.py, apk_package.py, gen_site.py, verify_apk.py |
| P-REL-114 | release flow | a straddled build shows each apks own bundle | as named | `test_P_REL_114_a_straddled_build_shows_each_apks_own_bundle` | gen_site.py, verify_apk.py, release_check.py, matrix.py; docs/flow-map/version-formats.md |
| P-REL-115 | release flow | the check reads the apks own line | as named | `test_P_REL_115_the_check_reads_the_apks_own_line` | gen_site.py, verify_apk.py, release_check.py, matrix.py; docs/flow-map/version-formats.md |
| P-REL-116 | release flow | the build line records the bundles | as named | `test_P_REL_116_the_build_line_records_the_bundles` | gen_site.py, verify_apk.py, release_check.py, matrix.py; docs/flow-map/version-formats.md |
| P-REL-120 | release flow | a lower code is refused and a pin or higher code is not | as named | `test_P_REL_120_a_lower_code_is_refused_and_a_pin_or_higher_code_is_not` | gen_site.py, verify_apk.py, release_check.py, matrix.py; docs/flow-map/version-formats.md |
| P-REL-121 | release flow | the bar is the highest code ever shipped | as named | `test_P_REL_121_the_bar_is_the_highest_code_ever_shipped` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-122 | release flow | the whole check deletes a lower code build | as named | `test_P_REL_122_the_whole_check_deletes_a_lower_code_build` | gen_site.py, verify_apk.py, release_check.py, matrix.py; docs/flow-map/version-formats.md |
| P-REL-117 | release flow | a lower update version a lower code or a new package is reported | as named | `test_P_REL_117_a_lower_update_version_a_lower_code_or_a_new_package_is_reported` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-118 | release flow | a backwards offer stays flagged until it is back above | as named | `test_P_REL_118_a_backwards_offer_stays_flagged_until_it_is_back_above` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-119 | release_check.py check_runs | a changed file outside the sync list is reported | as named | `test_P_REL_119_a_changed_file_outside_the_sync_list_is_reported` | release_check.py |
| P-HIS-01 | real version history | the highest tag is always the newest real one | as named | `test_P_HIS_01_the_highest_tag_is_always_the_newest_real_one` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-02 | real version history | every real file name gives its version | as named | `test_P_HIS_02_every_real_file_name_gives_its_version` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-03 | real version history | every real bundle moves the update version up | as named | `test_P_HIS_03_every_real_bundle_moves_the_update_version_up` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-04 | real version history | the formats seen are the formats known | as named | `test_P_HIS_04_the_formats_seen_are_the_formats_known` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-05 | real version history | after every real release the right build is offered | as named | `test_P_HIS_05_after_every_real_release_the_right_build_is_offered` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-06 | real version history | every real change reaches a phone through obtainx | as named | `test_P_HIS_06_every_real_change_reaches_a_phone_through_obtainx` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-07 | real version history | rebuilds with nothing new are not offered | as named | `test_P_HIS_07_rebuilds_with_nothing_new_are_not_offered` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-08 | real version history | the formats that broke or could break stay right in obtainx | as named | `test_P_HIS_08_the_formats_that_broke_or_could_break_stay_right_in_obtainx` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-09 | real version history | where things stand now | as named | `test_P_HIS_09_where_things_stand_now` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-10 | real version history | the number shown is the number inside | as named | `test_P_HIS_10_the_number_shown_is_the_number_inside` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-11 | real version history | every real apk has one key and a stable package | as named | `test_P_HIS_11_every_real_apk_has_one_key_and_a_stable_package` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-12 | real version history | the real cpu is the named cpu | as named | `test_P_HIS_12_the_real_cpu_is_the_named_cpu` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-13 | real version history | builds below the highest version code are the known ones and are refused | as named | `test_P_HIS_13_builds_below_the_highest_version_code_are_the_known_ones_and_are_refused` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-14 | real version history | every real asset name finds its app | as named | `test_P_HIS_14_every_real_asset_name_finds_its_app` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-15 | real version history | the real case offers the new versions and removes the old | as named | `test_P_HIS_15_the_real_case_offers_the_new_versions_and_removes_the_old` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-16 | real version history | a beta and its final in one release | as named | `test_P_HIS_16_a_beta_and_its_final_in_one_release` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-17 | real version history | every archived version is read as published | as named | `test_P_HIS_17_every_archived_version_is_read_as_published` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-18 | real version history | the versions only go up in the channels we follow | as named | `test_P_HIS_18_the_versions_only_go_up_in_the_channels_we_follow` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-19 | real version history | a new feed version starts a build and a built one does not | as named | `test_P_HIS_19_a_new_feed_version_starts_a_build_and_a_built_one_does_not` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-127 | release flow | the highest code of each app is read from every file | as named | `test_P_REL_127_the_highest_code_of_each_app_is_read_from_every_file` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-128 | release flow | an apk with no line in notes that have them claims no bundle | as named | `test_P_REL_128_an_apk_with_no_line_in_notes_that_have_them_claims_no_bundle` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-129 | release flow | the builder and both checks pick the same file of a two file release | as named | `test_P_REL_129_the_builder_and_both_checks_pick_the_same_file_of_a_two_file_release` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-20 | real version history | every real app gets the right files | as named | `test_P_HIS_20_every_real_app_gets_the_right_files` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-21 | real version history | what is not an update is known | as named | `test_P_HIS_21_what_is_not_an_update_is_known` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-HIS-22 | real version history | the real notes with each apks bundles are read | as named | `test_P_HIS_22_the_real_notes_with_each_apks_bundles_are_read` | gen_site.py, verify_apk.py, release_check.py, matrix.py, prebuilts.py |
| P-REL-98 | matrix.py check_builds_needed | a same day rebuild already on the patches is not repeated | as named | `test_P_REL_98_a_same_day_rebuild_already_on_the_patches_is_not_repeated` | matrix.py check_builds_needed |
| P-REL-99 | matrix.py _stremio_needs_build | a cancelled runs draft does not carry a version | as named | `test_P_REL_99_a_cancelled_runs_draft_does_not_carry_a_version` | matrix.py _stremio_needs_build |
| P-REL-95 | release_check.py | a build below the wanted version is reported | as named | `test_P_REL_95_a_build_below_the_wanted_version_is_reported` | release_check.py |
| P-REL-96 | release_check.py main | an unread page does not claim the offer is wrong | as named | `test_P_REL_96_an_unread_page_does_not_claim_the_offer_is_wrong` | release_check.py main |
| P-REL-97 | release_check.py main | flow test findings last until its next run | as named | `test_P_REL_97_flow_test_findings_last_until_its_next_run` | release_check.py main |

## Mode combinations

Not exercised by these tests, and proven by a real run instead: the bash steps of the workflows, GitHub's scheduler, and Pages itself. tools/release_check.py watches their results from outside every six hours.

Which switches and settings change these paths, and which combinations are exercised.

## Not exercised — justified

Written by `flowmap.py justify FILE:LINE CLASS "REASON"`. The anchor is the hash of that line's code: moving the line is fine,
changing its code fails the gate until the row is reviewed. Classes: `unreachable` (give the proof), `defensive` (what would have
to fail), `external` (where it IS exercised), `presentation` (only looks change). "Hard to test" is not a reason: write the test.

| Location | Anchor | Class | Reason |
|---|---|---|---|
