# Flow map — area `main`

Files covered: `tools/gen_site.py`, `tools/prune_release.py`, `tools/verify_apk.py`, `tools/release_check.py`, `tools/apk_package.py`, `src/scripts/matrix.py`, `src/core/patcher.py`, `src/core/builder.py`. Tests: `tests/test_release_flow.py`, `tests/test_version_history.py` (real formats: `version-formats.md`). Run: `python3 tools/flow/flowmap.py check`.

## Paths

One row per path, one test per row. The test's name or text holds the ID. "If it fails" is the first thing to check.

| ID | Entry | Conditions | Expected | Checks | If it fails |
|---|---|---|---|---|---|
| P-REL-01 | release flow | same day rebuild offers the highest version | as named | `test_P_REL_01_same_day_rebuild_offers_the_highest_version` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-02 | release flow | a newer release wins over an older one | as named | `test_P_REL_02_a_newer_release_wins_over_an_older_one` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-03 | release flow | a pin wins over a higher version | as named | `test_P_REL_03_a_pin_wins_over_a_higher_version` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-04 | release flow | the page offers the version inside the apk | as named | `test_P_REL_04_the_page_offers_the_version_inside_the_apk` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-05 | release flow | a builds version name keeps the order | as named | `test_P_REL_05_a_builds_version_name_keeps_the_order` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-06 | release flow | no bundle leaves the app version | as named | `test_P_REL_06_no_bundle_leaves_the_app_version` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-07 | release flow | an incomplete replacement replaces nothing | as named | `test_P_REL_07_an_incomplete_replacement_replaces_nothing` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-08 | release flow | api reads retry a cut off answer only | as named | `test_P_REL_08_api_reads_retry_a_cut_off_answer_only` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-09 | release flow | removed once the live site stopped offering it | as named | `test_P_REL_09_removed_once_the_live_site_stopped_offering_it` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-10 | release flow | kept while the live site still offers it | as named | `test_P_REL_10_kept_while_the_live_site_still_offers_it` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-11 | release flow | waits for pages to deploy | as named | `test_P_REL_11_waits_for_pages_to_deploy` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-12 | release flow | nothing superseded touches nothing | as named | `test_P_REL_12_nothing_superseded_touches_nothing` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-13 | release flow | a rebuild keeps the lines of apks it did not rebuild | as named | `test_P_REL_13_a_rebuild_keeps_the_lines_of_apks_it_did_not_rebuild` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-14 | release flow | the build job entry point writes the merged notes | as named | `test_P_REL_14_the_build_job_entry_point_writes_the_merged_notes` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-15 | release flow | delete and live urls use the real endpoints | as named | `test_P_REL_15_delete_and_live_urls_use_the_real_endpoints` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-16 | release flow | a good apk passes | as named | `test_P_REL_16_a_good_apk_passes` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-17 | release flow | the version inside must match the file name | as named | `test_P_REL_17_the_version_inside_must_match_the_file_name` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-18 | release flow | the libraries must be for the named cpu | as named | `test_P_REL_18_the_libraries_must_be_for_the_named_cpu` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-19 | release flow | the patch must be in the app | as named | `test_P_REL_19_the_patch_must_be_in_the_app` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-20 | release flow | the wrong key is refused | as named | `test_P_REL_20_the_wrong_key_is_refused` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-21 | release flow | the package must be the configured clone | as named | `test_P_REL_21_the_package_must_be_the_configured_clone` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-22 | release flow | junk never passes | as named | `test_P_REL_22_junk_never_passes` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-23 | release flow | a rejected apk is deleted and the job fails | as named | `test_P_REL_23_a_rejected_apk_is_deleted_and_the_job_fails` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-24 | release flow | nothing left means no notes for this job | as named | `test_P_REL_24_nothing_left_means_no_notes_for_this_job` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-25 | release flow | ci without the expected key fails | as named | `test_P_REL_25_ci_without_the_expected_key_fails` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-26 | release flow | config gives each clone and its patches | as named | `test_P_REL_26_config_gives_each_clone_and_its_patches` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-27 | release flow | the manifest reader gives the attributes | as named | `test_P_REL_27_the_manifest_reader_gives_the_attributes` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-28 | release flow | an app left on old patches is behind | as named | `test_P_REL_28_an_app_left_on_old_patches_is_behind` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-29 | release flow | two bundles after a straddled build count as behind | as named | `test_P_REL_29_two_bundles_after_a_straddled_build_count_as_behind` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-30 | release flow | a lower version build is retried | as named | `test_P_REL_30_a_lower_version_build_is_retried` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-31 | release flow | an app never built is behind | as named | `test_P_REL_31_an_app_never_built_is_behind` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-32 | release flow | a keyword app is left to its keywords | as named | `test_P_REL_32_a_keyword_app_is_left_to_its_keywords` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-33 | release flow | nothing new builds nothing | as named | `test_P_REL_33_nothing_new_builds_nothing` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-34 | release flow | a new patch release builds | as named | `test_P_REL_34_a_new_patch_release_builds` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-35 | release flow | a new stremio version builds | as named | `test_P_REL_35_a_new_stremio_version_builds` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-36 | release flow | a failed app is retried at most once a day | as named | `test_P_REL_36_a_failed_app_is_retried_at_most_once_a_day` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-37 | release flow | a failed comparison starts nothing | as named | `test_P_REL_37_a_failed_comparison_starts_nothing` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-38 | release flow | our newest release is found in any list order | as named | `test_P_REL_38_our_newest_release_is_found_in_any_list_order` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-39 | release flow | expected bundle is what a build would use | as named | `test_P_REL_39_expected_bundle_is_what_a_build_would_use` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-40 | release flow | prerelease labels keep their order | as named | `test_P_REL_40_prerelease_labels_keep_their_order` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-41 | release flow | a named patch that did not apply fails the build | as named | `test_P_REL_41_a_named_patch_that_did_not_apply_fails_the_build` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-42 | release flow | older versions come highest first | as named | `test_P_REL_42_older_versions_come_highest_first` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-43 | release flow | the next version down is built and marked | as named | `test_P_REL_43_the_next_version_down_is_built_and_marked` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-44 | release flow | never below what phones already have | as named | `test_P_REL_44_never_below_what_phones_already_have` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-45 | release flow | a named version does not fall back | as named | `test_P_REL_45_a_named_version_does_not_fall_back` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-46 | release flow | a working top version has no mark | as named | `test_P_REL_46_a_working_top_version_has_no_mark` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-47 | release flow | last shipped reads the newest build of this app | as named | `test_P_REL_47_last_shipped_reads_the_newest_build_of_this_app` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-48 | release flow | a healthy world has no problems | as named | `test_P_REL_48_a_healthy_world_has_no_problems` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-49 | release flow | the bug that started this is caught | as named | `test_P_REL_49_the_bug_that_started_this_is_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-50 | release flow | a missing app is caught | as named | `test_P_REL_50_a_missing_app_is_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-51 | release flow | a wrong update page is caught | as named | `test_P_REL_51_a_wrong_update_page_is_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-52 | release flow | an apk that is not what is promised is caught | as named | `test_P_REL_52_an_apk_that_is_not_what_is_promised_is_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-53 | release flow | release notes with no bundle are caught | as named | `test_P_REL_53_release_notes_with_no_bundle_are_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-54 | release flow | upstream ahead of the offer is caught | as named | `test_P_REL_54_upstream_ahead_of_the_offer_is_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-55 | release flow | the runs are checked | as named | `test_P_REL_55_the_runs_are_checked` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-56 | release flow | conflicts and unknown packages are caught | as named | `test_P_REL_56_conflicts_and_unknown_packages_are_caught` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-57 | release flow | a problem counts only after its grace | as named | `test_P_REL_57_a_problem_counts_only_after_its_grace` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-61 | release flow | healthy run is green and quiet | as named | `test_P_REL_61_healthy_run_is_green_and_quiet` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-62 | release flow | a problem turns the run red and alerts | as named | `test_P_REL_62_a_problem_turns_the_run_red_and_alerts` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-63 | release flow | a problem in its grace waits green | as named | `test_P_REL_63_a_problem_in_its_grace_waits_green` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-64 | release flow | unreadable releases judge nothing else | as named | `test_P_REL_64_unreadable_releases_judge_nothing_else` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-65 | release flow | a running build skips the check | as named | `test_P_REL_65_a_running_build_skips_the_check` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-67 | release flow | gather reads every source | as named | `test_P_REL_67_gather_reads_every_source` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-68 | release flow | a source that cannot be read is its own problem | as named | `test_P_REL_68_a_source_that_cannot_be_read_is_its_own_problem` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-69 | release flow | feed and bundles are read as a build would | as named | `test_P_REL_69_feed_and_bundles_are_read_as_a_build_would` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-70 | release flow | flow test failures are read from its log | as named | `test_P_REL_70_flow_test_failures_are_read_from_its_log` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-71 | release flow | read apk turns any failure into a finding | as named | `test_P_REL_71_read_apk_turns_any_failure_into_a_finding` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-72 | release flow | config gives the enabled apps | as named | `test_P_REL_72_config_gives_the_enabled_apps` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-73 | release flow | same day rebuild end to end | as named | `test_P_REL_73_same_day_rebuild_end_to_end` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-74 | release flow | a wrong key publishes nothing | as named | `test_P_REL_74_a_wrong_key_publishes_nothing` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-75 | release flow | a running build publishes nothing | as named | `test_P_REL_75_a_running_build_publishes_nothing` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-76 | release flow | package and signer over http | as named | `test_P_REL_76_package_and_signer_over_http` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-77 | release flow | a local file reads the same | as named | `test_P_REL_77_a_local_file_reads_the_same` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-78 | release flow | an unsigned or broken file is refused | as named | `test_P_REL_78_an_unsigned_or_broken_file_is_refused` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-79 | release flow | utf16 string pools read too | as named | `test_P_REL_79_utf16_string_pools_read_too` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-80 | release flow | the command line prints the answer | as named | `test_P_REL_80_the_command_line_prints_the_answer` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-81 | release flow | each app of the brand is listed | as named | `test_P_REL_81_each_app_of_the_brand_is_listed` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-82 | release flow | a dev brand is a prerelease | as named | `test_P_REL_82_a_dev_brand_is_a_prerelease` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-83 | release flow | an unknown source stops the build | as named | `test_P_REL_83_an_unknown_source_stops_the_build` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-84 | release flow | keywords filter only with the filter on | as named | `test_P_REL_84_keywords_filter_only_with_the_filter_on` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-85 | release flow | force builds every brand and no apps builds none | as named | `test_P_REL_85_force_builds_every_brand_and_no_apps_builds_none` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-86 | release flow | an unreadable upstream builds rather than misses | as named | `test_P_REL_86_an_unreadable_upstream_builds_rather_than_misses` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-87 | release flow | a removed patch repo skips that brand | as named | `test_P_REL_87_a_removed_patch_repo_skips_that_brand` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-88 | release flow | a brand with no release yet builds | as named | `test_P_REL_88_a_brand_with_no_release_yet_builds` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-89 | release flow | feed failures | as named | `test_P_REL_89_feed_failures` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-90 | release flow | the newest dev release is found by date | as named | `test_P_REL_90_the_newest_dev_release_is_found_by_date` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-91 | release flow | the command line runs the right check | as named | `test_P_REL_91_the_command_line_runs_the_right_check` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-92 | release flow | an apk still uploading is not offered | as named | `test_P_REL_92_an_apk_still_uploading_is_not_offered` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-93 | release flow | architectures are ordered by version | as named | `test_P_REL_93_architectures_are_ordered_by_version` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-94 | release flow | every enabled app has a stock signature to check | as named | `test_P_REL_94_every_enabled_app_has_a_stock_signature_to_check` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-100 | release flow | nothing uploads before the check | as named | `test_P_REL_100_nothing_uploads_before_the_check` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-101 | release flow | a rebuild never drafts a published release | as named | `test_P_REL_101_a_rebuild_never_drafts_a_published_release` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-102 | release flow | a crashed check cannot look like nothing new | as named | `test_P_REL_102_a_crashed_check_cannot_look_like_nothing_new` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-103 | release flow | the site prunes after publishing and health keeps its state | as named | `test_P_REL_103_the_site_prunes_after_publishing_and_health_keeps_its_state` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-104 | release flow | file names are read over http | as named | `test_P_REL_104_file_names_are_read_over_http` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-105 | release flow | live pages are read with retries | as named | `test_P_REL_105_live_pages_are_read_with_retries` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-106 | release flow | no apks leaves no mark | as named | `test_P_REL_106_no_apks_leaves_no_mark` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-107 | release flow | a straddled build is labelled with the lower bundle | as named | `test_P_REL_107_a_straddled_build_is_labelled_with_the_lower_bundle` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-108 | release flow | a pin wins over a newer release and a missing pin is reported | as named | `test_P_REL_108_a_pin_wins_over_a_newer_release_and_a_missing_pin_is_reported` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-109 | release flow | a final version beats its beta | as named | `test_P_REL_109_a_final_version_beats_its_beta` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-110 | release flow | what was shipped reads past a hyphenated cpu name | as named | `test_P_REL_110_what_was_shipped_reads_past_a_hyphenated_cpu_name` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-111 | release flow | a page not offering what the apk says is reported | as named | `test_P_REL_111_a_page_not_offering_what_the_apk_says_is_reported` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-112 | release flow | notes without its own bundle are reported | as named | `test_P_REL_112_notes_without_its_own_bundle_are_reported` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-113 | release flow | a tiny asset is not offered | as named | `test_P_REL_113_a_tiny_asset_is_not_offered` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-123 | release flow | a release with other files still gives the bundle | as named | `test_P_REL_123_a_release_with_other_files_still_gives_the_bundle` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-124 | release flow | a typed attribute that is no integer is skipped | as named | `test_P_REL_124_a_typed_attribute_that_is_no_integer_is_skipped` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-125 | release flow | releases are read page by page | as named | `test_P_REL_125_releases_are_read_page_by_page` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-126 | release flow | a pinned table is recognised | as named | `test_P_REL_126_a_pinned_table_is_recognised` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-114 | release flow | a straddled build shows each apks own bundle | as named | `test_P_REL_114_a_straddled_build_shows_each_apks_own_bundle` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-115 | release flow | the check reads the apks own line | as named | `test_P_REL_115_the_check_reads_the_apks_own_line` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-116 | release flow | the build line records the bundles | as named | `test_P_REL_116_the_build_line_records_the_bundles` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-120 | release flow | a lower code is refused and a pin or higher code is not | as named | `test_P_REL_120_a_lower_code_is_refused_and_a_pin_or_higher_code_is_not` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-121 | release flow | the bar is the highest code ever shipped | as named | `test_P_REL_121_the_bar_is_the_highest_code_ever_shipped` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-122 | release flow | the whole check deletes a lower code build | as named | `test_P_REL_122_the_whole_check_deletes_a_lower_code_build` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-117 | release flow | a lower update version a lower code or a new package is reported | as named | `test_P_REL_117_a_lower_update_version_a_lower_code_or_a_new_package_is_reported` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-118 | release flow | a backwards offer stays flagged until it is back above | as named | `test_P_REL_118_a_backwards_offer_stays_flagged_until_it_is_back_above` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-119 | release flow | a changed file outside the sync list is reported | as named | `test_P_REL_119_a_changed_file_outside_the_sync_list_is_reported` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-01 | real version history | the highest tag is always the newest real one | as named | `test_P_HIS_01_the_highest_tag_is_always_the_newest_real_one` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-02 | real version history | every real file name gives its version | as named | `test_P_HIS_02_every_real_file_name_gives_its_version` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-03 | real version history | every real bundle moves the update version up | as named | `test_P_HIS_03_every_real_bundle_moves_the_update_version_up` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-04 | real version history | the formats seen are the formats known | as named | `test_P_HIS_04_the_formats_seen_are_the_formats_known` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-05 | real version history | after every real release the right build is offered | as named | `test_P_HIS_05_after_every_real_release_the_right_build_is_offered` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-06 | real version history | every real change reaches a phone through obtainx | as named | `test_P_HIS_06_every_real_change_reaches_a_phone_through_obtainx` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-07 | real version history | rebuilds with nothing new are not offered | as named | `test_P_HIS_07_rebuilds_with_nothing_new_are_not_offered` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-08 | real version history | installed against offered is never unclear | as named | `test_P_HIS_08_installed_against_offered_is_never_unclear` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-09 | real version history | where things stand now | as named | `test_P_HIS_09_where_things_stand_now` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-10 | real version history | the number shown is the number inside | as named | `test_P_HIS_10_the_number_shown_is_the_number_inside` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-11 | real version history | every real apk has one key and a stable package | as named | `test_P_HIS_11_every_real_apk_has_one_key_and_a_stable_package` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-12 | real version history | the real cpu is the named cpu | as named | `test_P_HIS_12_the_real_cpu_is_the_named_cpu` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-13 | real version history | builds below the highest version code are the known ones and are refused | as named | `test_P_HIS_13_builds_below_the_highest_version_code_are_the_known_ones_and_are_refused` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-14 | real version history | every real asset name finds its app | as named | `test_P_HIS_14_every_real_asset_name_finds_its_app` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-15 | real version history | the real case offers the new versions and removes the old | as named | `test_P_HIS_15_the_real_case_offers_the_new_versions_and_removes_the_old` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-16 | real version history | a beta and its final in one release | as named | `test_P_HIS_16_a_beta_and_its_final_in_one_release` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-17 | real version history | every archived version is read as published | as named | `test_P_HIS_17_every_archived_version_is_read_as_published` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-18 | real version history | the versions only go up in the channels we follow | as named | `test_P_HIS_18_the_versions_only_go_up_in_the_channels_we_follow` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-19 | real version history | a new feed version starts a build and a built one does not | as named | `test_P_HIS_19_a_new_feed_version_starts_a_build_and_a_built_one_does_not` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-127 | release flow | the highest code of each app is read from every file | as named | `test_P_REL_127_the_highest_code_of_each_app_is_read_from_every_file` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-128 | release flow | an apk with no line in notes that have them claims no bundle | as named | `test_P_REL_128_an_apk_with_no_line_in_notes_that_have_them_claims_no_bundle` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-129 | release flow | the builder and both checks pick the same file of a two file release | as named | `test_P_REL_129_the_builder_and_both_checks_pick_the_same_file_of_a_two_file_release` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-20 | real version history | every real app gets the right files | as named | `test_P_HIS_20_every_real_app_gets_the_right_files` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-21 | real version history | what is not an update is known | as named | `test_P_HIS_21_what_is_not_an_update_is_known` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-HIS-22 | real version history | the real notes with each apks bundles are read | as named | `test_P_HIS_22_the_real_notes_with_each_apks_bundles_are_read` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-130 | release flow | the name is written and the rest survives | as named | `test_P_REL_130_the_name_is_written_and_the_rest_survives` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-131 | release flow | a typed version name and a utf16 pool are written too | as named | `test_P_REL_131_a_typed_version_name_and_a_utf16_pool_are_written_too` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-132 | release flow | a manifest it cannot read stops the build | as named | `test_P_REL_132_a_manifest_it_cannot_read_stops_the_build` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-133 | release flow | the builder names the version from the bundle it used | as named | `test_P_REL_133_the_builder_names_the_version_from_the_bundle_it_used` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-134 | release flow | the apk is named then signed | as named | `test_P_REL_134_the_apk_is_named_then_signed` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-135 | release flow | signing uses the real key settings or refuses | as named | `test_P_REL_135_signing_uses_the_real_key_settings_or_refuses` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-136 | release flow | the site reads each current build version from its apk | as named | `test_P_REL_136_the_site_reads_each_current_build_version_from_its_apk` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-137 | gen_site.py resolve_signers | an unreadable signer uses the same files record | as named | `test_P_REL_137_an_unreadable_signer_uses_the_same_files_record` | gen_site.py |
| P-REL-138 | gen_site.py resolve_versions | a file inside with no version uses the files version | as named | `test_P_REL_138_a_file_inside_with_no_version_uses_the_files_version` | gen_site.py |
| P-REL-139 | gen_site.py write_obtainium | an app sharing a package gets no entry | as named | `test_P_REL_139_an_app_sharing_a_package_gets_no_entry` | gen_site.py |
| P-REL-140 | builder._build_single | a wrong stock signature stops that app | as named | `test_P_REL_140_a_wrong_stock_signature_stops_that_app` | builder.py |
| P-REL-98 | release flow | a same day rebuild already on the patches is not repeated | as named | `test_P_REL_98_a_same_day_rebuild_already_on_the_patches_is_not_repeated` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-99 | release flow | a cancelled runs draft does not carry a version | as named | `test_P_REL_99_a_cancelled_runs_draft_does_not_carry_a_version` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-95 | release flow | a build below the wanted version is reported | as named | `test_P_REL_95_a_build_below_the_wanted_version_is_reported` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-96 | release flow | an unread page does not claim the offer is wrong | as named | `test_P_REL_96_an_unread_page_does_not_claim_the_offer_is_wrong` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-97 | release flow | flow test findings last until its next run | as named | `test_P_REL_97_flow_test_findings_last_until_its_next_run` | src/core/apk_version.py, gen_site.py, verify_apk.py, release_check.py |
| P-REL-141 | apk_package.morphe_versions | the real dex is read as morphe reads it | as named | `test_P_REL_141_the_real_dex_is_read_as_morphe_reads_it` | apk_package.py |
| P-REL-142 | apk_package.morphe_problem | a stable build that would alert is refused | as named | `test_P_REL_142_a_stable_build_that_would_alert_is_refused` | apk_package.py |
| P-REL-143 | verify_apk.problems | verify rejects it before upload | as named | `test_P_REL_143_verify_rejects_it_before_upload` | verify_apk.py |
| P-REL-144 | release_check._check_apk | health reads it from the live apk | as named | `test_P_REL_144_health_reads_it_from_the_live_apk` | release_check.py |
| P-REL-145 | apk_package.morphe_versions_from_url | health finds the class over http | as named | `test_P_REL_145_health_finds_the_class_over_http` | apk_package.py |
| P-REL-146 | patcher.report_stock_version | only dex files holding morphe code go through the tool | as named | `test_P_REL_146_only_dex_files_holding_morphe_code_go_through_the_tool` | src/core/patcher.py |
| P-REL-147 | apk_version.set_version_name | the new dex goes in and the real version is read first | as named | `test_P_REL_147_the_new_dex_goes_in_and_the_real_version_is_read_first` | src/core/apk_version.py |
| P-REL-148 | apk_version.update_version | a rebuild is higher only on its own bundle | as named | `test_P_REL_148_a_rebuild_is_higher_only_on_its_own_bundle` | src/core/apk_version.py |
| P-REL-149 | matrix.get_matrix | a manual build can name its apps | as named | `test_P_REL_149_a_manual_build_can_name_its_apps` | src/scripts/matrix.py, build.yml |
| P-REL-150 | gen_site.collect | an app not rebuilt stays offered from its older release | as named | `test_P_REL_150_an_app_not_rebuilt_stays_offered_from_its_older_release` | gen_site.py |

## Mode combinations

Not exercised by these tests, and proven by a real run instead: the bash steps of the workflows, GitHub's scheduler, and Pages itself. tools/release_check.py watches their results from outside every six hours.

Which switches and settings change these paths, and which combinations are exercised.

## Not exercised — justified

Written by `flowmap.py justify FILE:LINE CLASS "REASON"`. The anchor is the hash of that line's code: moving the line is fine,
changing its code fails the gate until the row is reviewed. Classes: `unreachable` (give the proof), `defensive` (what would have
to fail), `external` (where it IS exercised), `presentation` (only looks change). "Hard to test" is not a reason: write the test.

| Location | Anchor | Class | Reason |
|---|---|---|---|
| `src/core/apk_version.py:140` | `6d955a9d39` | external | a manifest string over 32767 characters: the same reader in tools/apk_package.py reads real APKs; no such string in the 117 real APKs |
| `src/core/apk_version.py:141` | `2f581d54a4` | external | same branch: a manifest string over 32767 characters |
| `src/core/apk_version.py:139` | `ac61e01912` | external | same branch: a manifest string over 32767 characters |
