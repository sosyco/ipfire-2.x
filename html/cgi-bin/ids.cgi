#!/usr/bin/perl
###############################################################################
#                                                                             #
# IPFire.org - A linux based firewall                                         #
# Copyright (C) 2007-2020  IPFire Team  <info@ipfire.org>                     #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

use strict;

# enable only the following on debugging purpose
#use warnings;
#use CGI::Carp 'fatalsToBrowser';

require '/var/ipfire/general-functions.pl';
require "${General::swroot}/lang.pl";
require "${General::swroot}/header.pl";
require "${General::swroot}/ids-functions.pl";

my %color = ();
my %mainsettings = ();
my %idsrules = ();
my %idssettings=();
my %rulessettings=();
my %rulesetsources = ();
my %cgiparams=();
my %checked=();
my %selected=();
my %ignored=();

# Read-in main settings, for language, theme and colors.
&General::readhash("${General::swroot}/main/settings", \%mainsettings);
&General::readhash("/srv/web/ipfire/html/themes/".$mainsettings{'THEME'}."/include/colors.txt", \%color);

# Get the available network zones, based on the config type of the system and store
# the list of zones in an array.
my @network_zones = &IDS::get_available_network_zones();

# Check if openvpn is started and add it to the array of network zones.
if ( -e "/var/run/openvpn.pid") {
	push(@network_zones, "ovpn");
}

my $errormessage;

# Create files if they does not exist yet.
&IDS::check_and_create_filelayout();

# Hash which contains the colour code of a network zone.
my %colourhash = (
	'red' => $Header::colourred,
	'green' => $Header::colourgreen,
	'blue' => $Header::colourblue,
	'orange' => $Header::colourorange,
	'ovpn' => $Header::colourovpn
);

&Header::showhttpheaders();

#Get GUI values
&Header::getcgihash(\%cgiparams);

## Add/edit an entry to the ignore file.
#
if (($cgiparams{'WHITELIST'} eq $Lang::tr{'add'}) || ($cgiparams{'WHITELIST'} eq $Lang::tr{'update'})) {

	# Check if any input has been performed.
	if ($cgiparams{'IGNORE_ENTRY_ADDRESS'} ne '') {

		# Check if the given input is no valid IP-address or IP-address with subnet, display an error message.
		if ((!&General::validip($cgiparams{'IGNORE_ENTRY_ADDRESS'})) && (!&General::validipandmask($cgiparams{'IGNORE_ENTRY_ADDRESS'}))) {
			$errormessage = "$Lang::tr{'guardian invalid address or subnet'}";
		}
	} else {
		$errormessage = "$Lang::tr{'guardian empty input'}";
	}

	# Go further if there was no error.
	if ($errormessage eq '') {
		my %ignored = ();
		my $id;
		my $status;

		# Assign hash values.
		my $new_entry_address = $cgiparams{'IGNORE_ENTRY_ADDRESS'};
		my $new_entry_remark = $cgiparams{'IGNORE_ENTRY_REMARK'};

		# Read-in ignoredfile.
		&General::readhasharray($IDS::ignored_file, \%ignored);

		# Check if we should edit an existing entry and got an ID.
		if (($cgiparams{'WHITELIST'} eq $Lang::tr{'update'}) && ($cgiparams{'ID'})) {
			# Assin the provided id.
			$id = $cgiparams{'ID'};

			# Undef the given ID.
			undef($cgiparams{'ID'});

			# Grab the configured status of the corresponding entry.
			$status = $ignored{$id}[2];
		} else {
			# Each newly added entry automatically should be enabled.
			$status = "enabled";

			# Generate the ID for the new entry.
			#
			# Sort the keys by their ID and store them in an array.
			my @keys = sort { $a <=> $b } keys %ignored;

			# Reverse the key array.
			my @reversed = reverse(@keys);

			# Obtain the last used id.
			my $last_id = @reversed[0];

			# Increase the last id by one and use it as id for the new entry.
			$id = ++$last_id;
		}

		# Add/Modify the entry to/in the ignored hash.
		$ignored{$id} = ["$new_entry_address", "$new_entry_remark", "$status"];

		# Write the changed ignored hash to the ignored file.
		&General::writehasharray($IDS::ignored_file, \%ignored);

		# Regenerate the ignore file.
		&IDS::generate_ignore_file();
	}

	# Check if the IDS is running.
	if(&IDS::ids_is_running()) {
		# Call suricatactrl to perform a reload.
		&IDS::call_suricatactrl("reload");
	}

## Toggle Enabled/Disabled for an existing entry on the ignore list.
#

} elsif ($cgiparams{'WHITELIST'} eq $Lang::tr{'toggle enable disable'}) {
	my %ignored = ();

	# Only go further, if an ID has been passed.
	if ($cgiparams{'ID'}) {
		# Assign the given ID.
		my $id = $cgiparams{'ID'};

		# Undef the given ID.
		undef($cgiparams{'ID'});

		# Read-in ignoredfile.
		&General::readhasharray($IDS::ignored_file, \%ignored);

		# Grab the configured status of the corresponding entry.
		my $status = $ignored{$id}[2];

		# Switch the status.
		if ($status eq "disabled") {
			$status = "enabled";
		} else {
			$status = "disabled";
		}

		# Modify the status of the existing entry.
		$ignored{$id} = ["$ignored{$id}[0]", "$ignored{$id}[1]", "$status"];

		# Write the changed ignored hash to the ignored file.
		&General::writehasharray($IDS::ignored_file, \%ignored);

		# Regenerate the ignore file.
		&IDS::generate_ignore_file();

		# Check if the IDS is running.
		if(&IDS::ids_is_running()) {
			# Call suricatactrl to perform a reload.
			&IDS::call_suricatactrl("reload");
		}
	}

## Remove entry from ignore list.
#
} elsif ($cgiparams{'WHITELIST'} eq $Lang::tr{'remove'}) {
	my %ignored = ();

	# Read-in ignoredfile.
	&General::readhasharray($IDS::ignored_file, \%ignored);

	# Drop entry from the hash.
	delete($ignored{$cgiparams{'ID'}});

	# Undef the given ID.
	undef($cgiparams{'ID'});

	# Write the changed ignored hash to the ignored file.
	&General::writehasharray($IDS::ignored_file, \%ignored);

	# Regenerate the ignore file.
	&IDS::generate_ignore_file();

	# Check if the IDS is running.
	if(&IDS::ids_is_running()) {
		# Call suricatactrl to perform a reload.
		&IDS::call_suricatactrl("reload");
	}
}

# Check if the page is locked, in this case, the ids_page_lock_file exists.
if (-e $IDS::ids_page_lock_file) {
	# Lock the webpage and print notice about autoupgrade of the ruleset
	# is in progess.
	&working_notice("$Lang::tr{'ids ruleset autoupdate in progress'}");

	# Loop and check if the file still exists.
	while(-e $IDS::ids_page_lock_file) {
		# Sleep for a second and re-check.
		sleep 1;
	}

	# Page has been unlocked, perform a reload.
	&reload();
}

# Check if any error has been stored.
if (-e $IDS::storederrorfile) {
        # Open file to read in the stored error message.
        open(FILE, "<$IDS::storederrorfile") or die "Could not open $IDS::storederrorfile. $!\n";

        # Read the stored error message.
        $errormessage = <FILE>;

        # Close file.
        close (FILE);

        # Delete the file, which is now not longer required.
        unlink($IDS::storederrorfile);
}

## Grab all available rules and store them in the idsrules hash.
#
# Open rules directory and do a directory listing.
opendir(DIR, $IDS::rulespath) or die $!;
	# Loop through the direcory.
	while (my $file = readdir(DIR)) {

		# We only want files.
		next unless (-f "$IDS::rulespath/$file");

		# Ignore empty files.
		next if (-z "$IDS::rulespath/$file");

		# Use a regular expression to find files ending in .rules
		next unless ($file =~ m/\.rules$/);

		# Ignore files which are not read-able.
		next unless (-R "$IDS::rulespath/$file");

		# Skip whitelist rules file.
		next if( $file eq "whitelist.rules");

		# Call subfunction to read-in rulefile and add rules to
		# the idsrules hash.
		&readrulesfile("$file");
	}

closedir(DIR);

# Gather used rulefiles.
#
# Check if the file for activated rulefiles is not empty.
if(-f $IDS::used_rulefiles_file) {
	# Open the file for used rulefile and read-in content.
	open(FILE, $IDS::used_rulefiles_file) or die "Could not open $IDS::used_rulefiles_file. $!\n";

	# Read-in content.
	my @lines = <FILE>;

	# Close file.
	close(FILE);

	# Loop through the array.
	foreach my $line (@lines) {
		# Remove newlines.
		chomp($line);

		# Skip comments.
		next if ($line =~ /\#/);

		# Skip blank  lines.
		next if ($line =~ /^\s*$/);

		# Gather rule sid and message from the ruleline.
		if ($line =~ /.*- (.*)/) {
			my $rulefile = $1;

			# Check if the current rulefile exists in the %idsrules hash.
			# If not, the file probably does not exist anymore or contains
			# no rules.
			if($idsrules{$rulefile}) {
				# Add the rulefile state to the %idsrules hash.
				$idsrules{$rulefile}{'Rulefile'}{'State'} = "on";
			}
		}
	}
}

# Save ruleset configuration.
if ($cgiparams{'RULESET'} eq $Lang::tr{'save'}) {
	my %oldsettings;
	my %rulesetsources;

	# Read-in current (old) IDS settings.
	&General::readhash("$IDS::rules_settings_file", \%oldsettings);

	# Get all available ruleset locations.
	&General::readhash("$IDS::rulesetsourcesfile", \%rulesetsources);

	# Prevent form name from been stored in conf file.
	delete $cgiparams{'RULESET'};

	# Grab the URL based on the choosen vendor.
	my $url = $rulesetsources{$cgiparams{'RULES'}};

	# Check if the choosen vendor (URL) requires an subscription/oinkcode.
	if ($url =~ /\<oinkcode\>/ ) {
		# Check if an subscription/oinkcode has been provided.
		if ($cgiparams{'OINKCODE'}) {
			# Check if the oinkcode contains unallowed chars.
			unless ($cgiparams{'OINKCODE'} =~ /^[a-z0-9]+$/) {
				$errormessage = $Lang::tr{'invalid input for oink code'};
			}
		} else {
			# Print an error message, that an subsription/oinkcode is required for this
			# vendor.
			$errormessage = $Lang::tr{'ids oinkcode required'};
		}
	}

	# Go on if there are no error messages.
	if (!$errormessage) {
		# Store settings into settings file.
		&General::writehash("$IDS::rules_settings_file", \%cgiparams);

		# Check if the the automatic rule update hass been touched.
		if($cgiparams{'AUTOUPDATE_INTERVAL'} ne $oldsettings{'AUTOUPDATE_INTERVAL'}) {
			# Call suricatactrl to set the new interval.
			&IDS::call_suricatactrl("cron", $cgiparams{'AUTOUPDATE_INTERVAL'});
		}

		# Check if a ruleset is present - if not or the source has been changed download it.
		if((! %idsrules) || ($oldsettings{'RULES'} ne $cgiparams{'RULES'})) {
			# Check if the red device is active.
			unless (-e "${General::swroot}/red/active") {
				$errormessage = "$Lang::tr{'could not download latest updates'} - $Lang::tr{'system is offline'}";
			}

			# Check if enough free disk space is availabe.
			if(&IDS::checkdiskspace()) {
				$errormessage = "$Lang::tr{'not enough disk space'}";
			}

			# Check if any errors happend.
			unless ($errormessage) {
				# Lock the webpage and print notice about downloading
				# a new ruleset.
				&working_notice("$Lang::tr{'ids working'}");

				# Write the modify sid's file and pass the taken ruleaction.
				&IDS::write_modify_sids_file();

				# Call subfunction to download the ruleset.
				if(&IDS::downloadruleset()) {
					$errormessage = $Lang::tr{'could not download latest updates'};

					# Call function to store the errormessage.
					&IDS::_store_error_message($errormessage);
				} else {
					# Call subfunction to launch oinkmaster.
					&IDS::oinkmaster();
				}

				# Check if the IDS is running.
				if(&IDS::ids_is_running()) {
					# Call suricatactrl to stop the IDS - because of the changed
					# ruleset - the use has to configure it before suricata can be
					# used again.
					&IDS::call_suricatactrl("stop");
				}

				# Perform a reload of the page.
				&reload();
			}
		}
	}

# Save ruleset.
} elsif ($cgiparams{'RULESET'} eq $Lang::tr{'ids apply'}) {
	# Arrays to store which rulefiles have been enabled and will be used.
	my @enabled_rulefiles;

	# Hash to store the user-enabled and disabled sids.
	my %enabled_disabled_sids;

	# Store if a restart of suricata is required.
	my $suricata_restart_required;

	# Loop through the hash of idsrules.
	foreach my $rulefile(keys %idsrules) {
		# Check if the state of the rulefile has been changed.
		unless ($cgiparams{$rulefile} eq $idsrules{$rulefile}{'Rulefile'}{'State'}) {
			# A restart of suricata is required to apply the changes of the used rulefiles.
			$suricata_restart_required = 1;
		}

		# Check if the rulefile is enabled.
		if ($cgiparams{$rulefile} eq "on") {
			# Add rulefile to the array of enabled rulefiles.
			push(@enabled_rulefiles, $rulefile);

			# Drop item from cgiparams hash.
			delete $cgiparams{$rulefile};
		}
	}

	# Read-in the files for enabled/disabled sids.
	# This will be done by calling the read_enabled_disabled_sids_file function two times
	# and merge the returned hashes together into the enabled_disabled_sids hash.
	%enabled_disabled_sids = (
		&read_enabled_disabled_sids_file($IDS::disabled_sids_file),
		&read_enabled_disabled_sids_file($IDS::enabled_sids_file));

	# Loop through the hash of idsrules.
	foreach my $rulefile (keys %idsrules) {
		# Loop through the single rules of the rulefile.
		foreach my $sid (keys %{$idsrules{$rulefile}}) {
			# Skip the current sid if it is not numeric.
			next unless ($sid =~ /\d+/ );

			# Check if there exists a key in the cgiparams hash for this sid.
			if (exists($cgiparams{$sid})) {
				# Look if the rule is disabled.
				if ($idsrules{$rulefile}{$sid}{'State'} eq "off") {
					# Check if the state has been set to 'on'.
					if ($cgiparams{$sid} eq "on") {
						# Add/Modify the sid to/in the enabled_disabled_sids hash.
						$enabled_disabled_sids{$sid} = "enabled";

						# Drop item from cgiparams hash.
						delete $cgiparams{$rulefile}{$sid};
					}
				}
			} else {
				# Look if the rule is enabled.
				if ($idsrules{$rulefile}{$sid}{'State'} eq "on") {
					# Check if the state is 'on' and should be disabled.
					# In this case there is no entry
					# for the sid in the cgiparams hash.
					# Add/Modify it to/in the enabled_disabled_sids hash.
					$enabled_disabled_sids{$sid} = "disabled";

					# Drop item from cgiparams hash.
					delete $cgiparams{$rulefile}{$sid};
				}
			}
		}
	}

	# Open enabled sid's file for writing.
	open(ENABLED_FILE, ">$IDS::enabled_sids_file") or die "Could not write to $IDS::enabled_sids_file. $!\n";

	# Open disabled sid's file for writing.
	open(DISABLED_FILE, ">$IDS::disabled_sids_file") or die "Could not write to $IDS::disabled_sids_file. $!\n";

	# Write header to the files.
	print ENABLED_FILE "#Autogenerated file. Any custom changes will be overwritten!\n";
	print DISABLED_FILE "#Autogenerated file. Any custom changes will be overwritten!\n";

	# Check if the hash for enabled/disabled files contains any entries.
	if (%enabled_disabled_sids) {
		# Loop through the hash.
		foreach my $sid (keys %enabled_disabled_sids) {
			# Check if the sid is enabled.
			if ($enabled_disabled_sids{$sid} eq "enabled") {
				# Print the sid to the enabled_sids file.
				print ENABLED_FILE "enablesid $sid\n";
			# Check if the sid is disabled.
			} elsif ($enabled_disabled_sids{$sid} eq "disabled") {
				# Print the sid to the disabled_sids file.
				print DISABLED_FILE "disablesid $sid\n";
			# Something strange happende - skip the current sid.
			} else {
				next;
			}
		}
	}

	# Close file for enabled_sids after writing.
	close(ENABLED_FILE);

	# Close file for disabled_sids after writing.
	close(DISABLED_FILE);

	# Call function to generate and write the used rulefiles file.
	&IDS::write_used_rulefiles_file(@enabled_rulefiles);

	# Lock the webpage and print message.
	&working_notice("$Lang::tr{'ids apply ruleset changes'}");

	# Call oinkmaster to alter the ruleset.
	&IDS::oinkmaster();

	# Check if the IDS is running.
	if(&IDS::ids_is_running()) {
		# Check if a restart of suricata is required.
		if ($suricata_restart_required) {
			# Call suricatactrl to perform the restart.
			&IDS::call_suricatactrl("restart");
		} else {
			# Call suricatactrl to perform a reload.
			&IDS::call_suricatactrl("reload");
		}
	}

	# Reload page.
	&reload();

# Download new ruleset.
} elsif ($cgiparams{'RULESET'} eq $Lang::tr{'update ruleset'}) {
	# Check if the red device is active.
	unless (-e "${General::swroot}/red/active") {
		$errormessage = "$Lang::tr{'could not download latest updates'} - $Lang::tr{'system is offline'}";
	}

	# Check if enought free disk space is availabe.
	if(&IDS::checkdiskspace()) {
		$errormessage = "$Lang::tr{'not enough disk space'}";
	}

	# Check if any errors happend.
	unless ($errormessage) {
		# Lock the webpage and print notice about downloading
		# a new ruleset.
		&working_notice("$Lang::tr{'ids download new ruleset'}");

		# Call subfunction to download the ruleset.
		if(&IDS::downloadruleset()) {
			$errormessage = $Lang::tr{'could not download latest updates'};

			# Call function to store the errormessage.
			&IDS::_store_error_message($errormessage);

			# Preform a reload of the page.
			&reload();
		} else {
			# Call subfunction to launch oinkmaster.
			&IDS::oinkmaster();

			# Check if the IDS is running.
			if(&IDS::ids_is_running()) {
				# Call suricatactrl to perform a reload.
				&IDS::call_suricatactrl("reload");
			}

			# Perform a reload of the page.
			&reload();
		}
	}
# Save IDS settings.
} elsif ($cgiparams{'IDS'} eq $Lang::tr{'save'}) {
	my %oldidssettings;
	my $reload_page;
	my $monitored_zones = 0;

	# Read-in current (old) IDS settings.
	&General::readhash("$IDS::ids_settings_file", \%oldidssettings);

	# Prevent form name from been stored in conf file.
	delete $cgiparams{'IDS'};

	# Check if the IDS should be enabled.
	if ($cgiparams{'ENABLE_IDS'} eq "on") {
		# Check if any ruleset is available. Otherwise abort and display an error.
		unless(%idsrules) {
			$errormessage = $Lang::tr{'ids no ruleset available'};
		}

		# Loop through the array of available interfaces.
		foreach my $zone (@network_zones) {
			# Convert interface name into upper case.
			my $zone_upper = uc($zone);

			# Check if the IDS is enabled for this interaces.
			if ($cgiparams{"ENABLE_IDS_$zone_upper"}) {
				# Increase count.
				$monitored_zones++;
			}
		}

		# Check if at least one zone should be monitored, or show an error.
		unless ($monitored_zones >= 1) {
			$errormessage = $Lang::tr{'ids no network zone'};
		}
	}

	# Go on if there are no error messages.
	if (!$errormessage) {
		# Store settings into settings file.
		&General::writehash("$IDS::ids_settings_file", \%cgiparams);
	}

	# Generate file to store the home net.
	&IDS::generate_home_net_file();

	# Generate file to the store the DNS servers.
	&IDS::generate_dns_servers_file();

	# Generate file to store the HTTP ports.
	&IDS::generate_http_ports_file();

	# Write the modify sid's file and pass the taken ruleaction.
	&IDS::write_modify_sids_file();

	# Check if "MONITOR_TRAFFIC_ONLY" has been changed.
	if($cgiparams{'MONITOR_TRAFFIC_ONLY'} ne $oldidssettings{'MONITOR_TRAFFIC_ONLY'}) {
		# Check if a ruleset exists.
		if (%idsrules) {
			# Lock the webpage and print message.
			&working_notice("$Lang::tr{'ids working'}");

			# Call oinkmaster to alter the ruleset.
			&IDS::oinkmaster();

			# Set reload_page to "True".
			$reload_page="True";
		}
	}

	# Check if the IDS currently is running.
	if(&IDS::ids_is_running()) {
		# Check if ENABLE_IDS is set to on.
		if($cgiparams{'ENABLE_IDS'} eq "on") {
			# Call suricatactrl to perform a reload of suricata.
			&IDS::call_suricatactrl("reload");
		} else {
			# Call suricatactrl to stop suricata.
			&IDS::call_suricatactrl("stop");
		}
	} else {
		# Call suricatactrl to start suricata.
		&IDS::call_suricatactrl("start");
	}

	# Check if the page should be reloaded.
	if ($reload_page) {
		# Perform a reload of the page.
		&reload();
	}
}

# Read-in idssettings and rulesetsettings
&General::readhash("$IDS::ids_settings_file", \%idssettings);
&General::readhash("$IDS::rules_settings_file", \%rulessettings);

# If no autoupdate intervall has been configured yet, set default value.
unless(exists($rulessettings{'AUTOUPDATE_INTERVAL'})) {
	# Set default to "weekly".
	$rulessettings{'AUTOUPDATE_INTERVAL'} = 'weekly';
}

# Read-in ignored hosts.
&General::readhasharray("$IDS::settingsdir/ignored", \%ignored);

$checked{'ENABLE_IDS'}{'off'} = '';
$checked{'ENABLE_IDS'}{'on'} = '';
$checked{'ENABLE_IDS'}{$idssettings{'ENABLE_IDS'}} = "checked='checked'";
$checked{'MONITOR_TRAFFIC_ONLY'}{'off'} = '';
$checked{'MONITOR_TRAFFIC_ONLY'}{'on'} = '';
$checked{'MONITOR_TRAFFIC_ONLY'}{$idssettings{'MONITOR_TRAFFIC_ONLY'}} = "checked='checked'";
$selected{'RULES'}{'nothing'} = '';
$selected{'RULES'}{'community'} = '';
$selected{'RULES'}{'emerging'} = '';
$selected{'RULES'}{'registered'} = '';
$selected{'RULES'}{'subscripted'} = '';
$selected{'RULES'}{$rulessettings{'RULES'}} = "selected='selected'";
$selected{'AUTOUPDATE_INTERVAL'}{'off'} = '';
$selected{'AUTOUPDATE_INTERVAL'}{'daily'} = '';
$selected{'AUTOUPDATE_INTERVAL'}{'weekly'} = '';
$selected{'AUTOUPDATE_INTERVAL'}{$rulessettings{'AUTOUPDATE_INTERVAL'}} = "selected='selected'";

&Header::openpage($Lang::tr{'intrusion detection system'}, 1, '');

### Java Script ###
print"<script>\n";

# Java script variable declaration for show and hide.
print"var show = \"$Lang::tr{'ids show'}\"\;\n";
print"var hide = \"$Lang::tr{'ids hide'}\"\;\n";

print <<END
	// Java Script function to show/hide the text input field for
	// Oinkcode/Subscription code.
	var update_code = function() {
		if(\$('#RULES').val() == 'registered') {
			\$('#code').show();
		} else if(\$('#RULES').val() == 'subscripted') {
			\$('#code').show();
		} else if(\$('#RULES').val() == 'emerging_pro') {
			\$('#code').show();
		} else {
			\$('#code').hide();
		}
	};

	// JQuery function to call corresponding function when
	// the ruleset is changed or the page is loaded for showing/hiding
	// the code area.
	\$(document).ready(function() {
		\$('#RULES').change(update_code);
		update_code();
	});

	// Tiny java script function to show/hide the rules
	// of a given category.
	function showhide(tblname) {
		\$("#" + tblname).toggle();

		// Get current content of the span element.
		var content = document.getElementById("span_" + tblname);

		if (content.innerHTML === show) {
			content.innerHTML = hide;
		} else {
			content.innerHTML = show;
		}
	}
</script>
END
;

&Header::openbigbox('100%', 'left', '', $errormessage);

if ($errormessage) {
	&Header::openbox('100%', 'left', $Lang::tr{'error messages'});
	print "<class name='base'>$errormessage\n";
	print "&nbsp;</class>\n";
	&Header::closebox();
}

# Draw current state of the IDS
&Header::openbox('100%', 'left', $Lang::tr{'intrusion detection system'});

# Check if the IDS is running and obtain the process-id.
my $pid = &IDS::ids_is_running();

# Display some useful information, if suricata daemon is running.
if ($pid) {
	# Gather used memory.
	my $memory = &get_memory_usage($pid);

	print <<END;
		<table width='95%' cellspacing='0' class='tbl'>
			<tr>
				<th bgcolor='$color{'color20'}' colspan='3' align='left'><strong>$Lang::tr{'intrusion detection'}</strong></th>
			</tr>

			<tr>
				<td class='base'>$Lang::tr{'guardian daemon'}</td>
				<td align='center' colspan='2' width='75%' bgcolor='${Header::colourgreen}'><font color='white'><strong>$Lang::tr{'running'}</strong></font></td>
			</tr>

			<tr>
				<td class='base'></td>
				<td bgcolor='$color{'color20'}' align='center'><strong>PID</strong></td>
				<td bgcolor='$color{'color20'}' align='center'><strong>$Lang::tr{'memory'}</strong></td>
			</tr>

			<tr>
				<td class='base'></td>
				<td bgcolor='$color{'color22'}' align='center'>$pid</td>
				<td bgcolor='$color{'color22'}' align='center'>$memory KB</td>
			</tr>
		</table>
END
} else {
	# Otherwise display a hint that the service is not launched.
	print <<END;
		<table width='95%' cellspacing='0' class='tbl'>
			<tr>
				<th bgcolor='$color{'color20'}' colspan='3' align='left'><strong>$Lang::tr{'intrusion detection'}</strong></th>
			</tr>

			<tr>
				<td class='base'>$Lang::tr{'guardian daemon'}</td>
				<td align='center' width='75%' bgcolor='${Header::colourred}'><font color='white'><strong>$Lang::tr{'stopped'}</strong></font></td>
			</tr>
		</table>
END
}

# Only show this area, if a ruleset is present.
if (%idsrules) {

	print <<END

	<br><br><h2>$Lang::tr{'settings'}</h2>

	<form method='post' action='$ENV{'SCRIPT_NAME'}'>
		<table width='100%' border='0'>
			<tr>
				<td class='base' colspan='2'>
					<input type='checkbox' name='ENABLE_IDS' $checked{'ENABLE_IDS'}{'on'}>&nbsp;$Lang::tr{'ids enable'}
				</td>

				<td class='base' colspan='2'>
					<input type='checkbox' name='MONITOR_TRAFFIC_ONLY' $checked{'MONITOR_TRAFFIC_ONLY'}{'on'}>&nbsp;$Lang::tr{'ids monitor traffic only'}
			</td>
			</tr>

			<tr>
				<td><br><br></td>
				<td><br><br></td>
				<td><br><br></td>
				<td><br><br></td>
			</tr>

			<tr>
				<td colspan='4'><b>$Lang::tr{'ids monitored interfaces'}</b><br></td>
			</tr>

			<tr>
END
;

	# Loop through the array of available networks and print config options.
	foreach my $zone (@network_zones) {
		my $checked_input;
		my $checked_forward;

		# Convert current zone name to upper case.
		my $zone_upper = uc($zone);

		# Set zone name.
		my $zone_name = $zone;

		# Dirty hack to get the correct language string for the red zone.
		if ($zone eq "red") {
			$zone_name = "red1";
		}

		# Grab checkbox status from settings hash.
		if ($idssettings{"ENABLE_IDS_$zone_upper"} eq "on") {
			$checked_input = "checked = 'checked'";
		}

		print "<td class='base' width='20%'>\n";
		print "<input type='checkbox' name='ENABLE_IDS_$zone_upper' $checked_input>\n";
		print "&nbsp;$Lang::tr{'enabled on'}<font color='$colourhash{$zone}'> $Lang::tr{$zone_name}</font>\n";
		print "</td>\n";
	}

print <<END
			</tr>
		</table>

		<br><br>

		<table width='100%'>
			<tr>
				<td align='right'><input type='submit' name='IDS' value='$Lang::tr{'save'}' /></td>
			</tr>
		</table>
	</form>
END
;

}

&Header::closebox();

# Draw elements for ruleset configuration.
&Header::openbox('100%', 'center', $Lang::tr{'ids ruleset settings'});

print <<END
<form method='post' action='$ENV{'SCRIPT_NAME'}'>
        <table width='100%' border='0'>
		<tr>
			<td><b>$Lang::tr{'ids rules update'}</b></td>
			<td><b>$Lang::tr{'ids automatic rules update'}</b></td>
		</tr>

		<tr>
			<td><select name='RULES' id='RULES'>
				<option value='emerging' $selected{'RULES'}{'emerging'} >$Lang::tr{'emerging rules'}</option>
				<option value='emerging_pro' $selected{'RULES'}{'emerging_pro'} >$Lang::tr{'emerging pro rules'}</option>
				<option value='community' $selected{'RULES'}{'community'} >$Lang::tr{'community rules'}</option>
				<option value='registered' $selected{'RULES'}{'registered'} >$Lang::tr{'registered user rules'}</option>
				<option value='subscripted' $selected{'RULES'}{'subscripted'} >$Lang::tr{'subscripted user rules'}</option>
			</select>
			</td>

			<td>
				<select name='AUTOUPDATE_INTERVAL'>
					<option value='off' $selected{'AUTOUPDATE_INTERVAL'}{'off'} >- $Lang::tr{'Disabled'} -</option>
					<option value='daily' $selected{'AUTOUPDATE_INTERVAL'}{'daily'} >$Lang::tr{'Daily'}</option>
					<option value='weekly' $selected{'AUTOUPDATE_INTERVAL'}{'weekly'} >$Lang::tr{'Weekly'}</option>
				</select>
			</td>
		</tr>

		<tr>
			<td colspan='2'><br><br></td>
		</tr>

		<tr style='display:none' id='code'>
			<td colspan='2'>Oinkcode:&nbsp;<input type='text' size='40' name='OINKCODE' value='$rulessettings{'OINKCODE'}'></td>
		</tr>

		<tr>
			<td>&nbsp;</td>

			<td align='right'>
END
;
			# Show the "Update Ruleset"-Button only if a ruleset has been downloaded yet and automatic updates are disabled.
			if ((%idsrules) && ($rulessettings{'AUTOUPDATE_INTERVAL'} eq "off")) {
				# Display button to update the ruleset.
				print"<input type='submit' name='RULESET' value='$Lang::tr{'update ruleset'}'>\n";
		}
print <<END;
				<input type='submit' name='RULESET' value='$Lang::tr{'save'}'>
			</td>

		</tr>
	</table>
</form>
END
;

&Header::closebox();

#
# Whitelist / Ignorelist
#
&Header::openbox('100%', 'center', $Lang::tr{'ids ignored hosts'});

print <<END;
	<table width='100%'>
		<tr>
			<td class='base' bgcolor='$color{'color20'}'><b>$Lang::tr{'ip address'}</b></td>
			<td class='base' bgcolor='$color{'color20'}'><b>$Lang::tr{'remark'}</b></td>
			<td class='base' colspan='3' bgcolor='$color{'color20'}'></td>
		</tr>
END
		# Check if some hosts have been added to be ignored.
		if (keys (%ignored)) {
			my $col = "";

			# Loop through all entries of the hash.
			while( (my $key) = each %ignored)  {
				# Assign data array positions to some nice variable names.
				my $address = $ignored{$key}[0];
				my $remark = $ignored{$key}[1];
				my $status  = $ignored{$key}[2];

				# Check if the key (id) number is even or not.
				if ($cgiparams{'ID'} eq $key) {
					$col="bgcolor='${Header::colouryellow}'";
				} elsif ($key % 2) {
					$col="bgcolor='$color{'color22'}'";
				} else {
					$col="bgcolor='$color{'color20'}'";
				}

				# Choose icon for the checkbox.
				my $gif;
				my $gdesc;

				# Check if the status is enabled and select the correct image and description.
				if ($status eq 'enabled' ) {
					$gif = 'on.gif';
					$gdesc = $Lang::tr{'click to disable'};
				} else {
					$gif = 'off.gif';
					$gdesc = $Lang::tr{'click to enable'};
				}

print <<END;
				<tr>
					<td width='20%' class='base' $col>$address</td>
					<td width='65%' class='base' $col>$remark</td>

					<td align='center' $col>
						<form method='post' action='$ENV{'SCRIPT_NAME'}'>
							<input type='hidden' name='WHITELIST' value='$Lang::tr{'toggle enable disable'}' />
							<input type='image' name='$Lang::tr{'toggle enable disable'}' src='/images/$gif' alt='$gdesc' title='$gdesc' />
							<input type='hidden' name='ID' value='$key' />
						</form>
					</td>

					<td align='center' $col>
						<form method='post' action='$ENV{'SCRIPT_NAME'}'>
							<input type='hidden' name='WHITELIST' value='$Lang::tr{'edit'}' />
							<input type='image' name='$Lang::tr{'edit'}' src='/images/edit.gif' alt='$Lang::tr{'edit'}' title='$Lang::tr{'edit'}' />
							<input type='hidden' name='ID' value='$key' />
						</form>
					</td>

					<td align='center' $col>
						<form method='post' name='$key' action='$ENV{'SCRIPT_NAME'}'>
							<input type='image' name='$Lang::tr{'remove'}' src='/images/delete.gif' title='$Lang::tr{'remove'}' alt='$Lang::tr{'remove'}'>
							<input type='hidden' name='ID' value='$key'>
							<input type='hidden' name='WHITELIST' value='$Lang::tr{'remove'}'>
						</form>
					</td>
				</tr>
END
			}
		} else {
			# Print notice that currently no hosts are ignored.
			print "<tr>\n";
			print "<td class='base' colspan='2'>$Lang::tr{'guardian no entries'}</td>\n";
			print "</tr>\n";
		}

	print "</table>\n";

	# Section to add new elements or edit existing ones.
print <<END;
	<br>
	<hr>
	<br>

	<div align='center'>
		<table width='100%'>
END

	# Assign correct headline and button text.
	my $buttontext;
	my $entry_address;
	my $entry_remark;

	# Check if an ID (key) has been given, in this case an existing entry should be edited.
	if ($cgiparams{'ID'} ne '') {
		$buttontext = $Lang::tr{'update'};
			print "<tr><td class='boldbase' colspan='3'><b>$Lang::tr{'update'}</b></td></tr>\n";

			# Grab address and remark for the given key.
			$entry_address = $ignored{$cgiparams{'ID'}}[0];
			$entry_remark = $ignored{$cgiparams{'ID'}}[1];
		} else {
			$buttontext = $Lang::tr{'add'};
			print "<tr><td class='boldbase' colspan='3'><b>$Lang::tr{'dnsforward add a new entry'}</b></td></tr>\n";
		}

print <<END;
			<form method='post' action='$ENV{'SCRIPT_NAME'}'>
			<input type='hidden' name='ID' value='$cgiparams{'ID'}'>
			<tr>
				<td width='30%'>$Lang::tr{'ip address'}: </td>
				<td width='50%'><input type='text' name='IGNORE_ENTRY_ADDRESS' value='$entry_address' size='24' /></td>

				<td width='30%'>$Lang::tr{'remark'}: </td>
				<td wicth='50%'><input type='text' name=IGNORE_ENTRY_REMARK value='$entry_remark' size='24' /></td>
				<td align='center' width='20%'><input type='submit' name='WHITELIST' value='$buttontext' /></td>
			</tr>
			</form>
		</table>
	</div>
END

&Header::closebox();

# Only show the section for configuring the ruleset if one is present.
if (%idsrules) {
	# Load neccessary perl modules for file stat and to format the timestamp.
	use File::stat;
	use POSIX qw( strftime );

	# Call stat on the rulestarball.
	my $stat = stat("$IDS::rulestarball");

	# Get timestamp the file creation.
	my $mtime = $stat->mtime;

	# Convert into human read-able format.
	my $rulesdate = strftime('%Y-%m-%d %H:%M:%S', localtime($mtime));

	&Header::openbox('100%', 'LEFT', "$Lang::tr{'intrusion detection system rules'} ($rulesdate)" );

		print"<form method='POST' action='$ENV{'SCRIPT_NAME'}'>\n";

		# Output display table for rule files
		print "<table width='100%'>\n";

		# Loop over each rule file
		foreach my $rulefile (sort keys(%idsrules)) {
			my $rulechecked = '';

			# Check if rule file is enabled
			if ($idsrules{$rulefile}{'Rulefile'}{'State'} eq 'on') {
				$rulechecked = 'CHECKED';
			}

			# Convert rulefile name into category name.
			my $categoryname = &_rulefile_to_category($rulefile);

			# Table and rows for the rule files.
			print"<tr>\n";
			print"<td class='base' width='5%'>\n";
			print"<input type='checkbox' name='$rulefile' $rulechecked>\n";
			print"</td>\n";
			print"<td class='base' width='90%'><b>$rulefile</b></td>\n";
			print"<td class='base' width='5%' align='right'>\n";
			print"<a href=\"javascript:showhide('$categoryname')\"><span id='span_$categoryname'>$Lang::tr{'ids show'}</span></a>\n";
			print"</td>\n";
			print"</tr>\n";

			# Rows which will be hidden per default and will contain the single rules.
			print"<tr  style='display:none' id='$categoryname'>\n";
			print"<td colspan='3'>\n";

			# Local vars
			my $lines;
			my $rows;
			my $col;

			# New table for the single rules.
			print "<table width='100%'>\n";

			# Loop over rule file rules
			foreach my $sid (sort {$a <=> $b} keys(%{$idsrules{$rulefile}})) {
				# Local vars
				my $ruledefchecked = '';

				# Skip rulefile itself.
				next if ($sid eq "Rulefile");

				# If 2 rules have been displayed, start a new row
				if (($lines % 2) == 0) {
					print "</tr><tr>\n";

					# Increase rows by once.
					$rows++;
				}

				# Colour lines.
				if ($rows % 2) {
					$col="bgcolor='$color{'color20'}'";
				} else {
					$col="bgcolor='$color{'color22'}'";
				}

				# Set rule state
				if ($idsrules{$rulefile}{$sid}{'State'} eq 'on') {
					$ruledefchecked = 'CHECKED';
				}

				# Create rule checkbox and display rule description
				print "<td class='base' width='5%' align='right' $col>\n";
				print "<input type='checkbox' NAME='$sid' $ruledefchecked>\n";
				print "</td>\n";
				print "<td class='base' width='45%' $col>$idsrules{$rulefile}{$sid}{'Description'}</td>";

				# Increment rule count
				$lines++;
			}

			# If do not have a second rule for row, create empty cell
			if (($lines % 2) != 0) {
				print "<td class='base'></td>";
			}

			# Close display table
			print "</tr></table></td></tr>";
		}

		# Close display table
		print "</table>";

print <<END
<table width='100%'>
<tr>
	<td width='100%' align='right'><input type='submit' name='RULESET' value='$Lang::tr{'ids apply'}'></td>
</tr>
</table>
</form>
END
;
	&Header::closebox();
}

&Header::closebigbox();
&Header::closepage();

#
## A function to display a notice, to lock the webpage and
## tell the user which action currently will be performed.
#
sub working_notice ($) {
	my ($message) = @_;

	&Header::openpage($Lang::tr{'intrusion detection system'}, 1, '');
	&Header::openbigbox('100%', 'left', '', $errormessage);
	&Header::openbox( 'Waiting', 1,);
		print <<END;
			<table>
				<tr>
					<td><img src='/images/indicator.gif' alt='$Lang::tr{'aktiv'}' /></td>
					<td>$message</td>
				</tr>
			</table>
END
	&Header::closebox();
	&Header::closebigbox();
	&Header::closepage();
}

#
## A tiny function to perform a reload of the webpage after one second.
#
sub reload () {
	print "<meta http-equiv='refresh' content='1'>\n";

	# Stop the script.
	exit;
}

#
## Private function to read-in and parse rules of a given rulefile.
#
## The given file will be read, parsed and all valid rules will be stored by ID,
## message/description and it's state in the idsrules hash.
#
sub readrulesfile ($) {
	my $rulefile = shift;

	# Open rule file and read in contents
	open(RULEFILE, "$IDS::rulespath/$rulefile") or die "Unable to read $rulefile!";

	# Store file content in an array.
	my @lines = <RULEFILE>;

	# Close file.
	close(RULEFILE);

	# Loop over rule file contents
	foreach my $line (@lines) {
		# Remove whitespaces.
		chomp $line;

		# Skip blank  lines.
		next if ($line =~ /^\s*$/);

		# Local vars.
		my $sid;
		my $msg;

		# Gather rule sid and message from the ruleline.
		if ($line =~ m/.*msg:\"(.*?)\"\; .* sid:(.*?); /) {
			$msg = $1;
			$sid = $2;

			# Check if a rule has been found.
			if ($sid && $msg) {
				# Add rule to the idsrules hash.
				$idsrules{$rulefile}{$sid}{'Description'} = $msg;

				# Grab status of the rule. Check if ruleline starts with a "dash".
				if ($line =~ /^\#/) {
					# If yes, the rule is disabled.
					$idsrules{$rulefile}{$sid}{'State'} = "off";
				} else {
					# Otherwise the rule is enabled.
					$idsrules{$rulefile}{$sid}{'State'} = "on";
				}
			}
		}
	}
}

#
## Function to get the used memory of a given process-id.
#
sub get_memory_usage($) {
	my ($pid) = @_;

	my $memory = 0;

	# Try to open the status file for the given process-id on the pseudo
	# file system proc.
	if (open(FILE, "/proc/$pid/status")) {
		# Loop through the entire file.
		while (<FILE>) {
			# Splitt current line content and store them into variables.
			my ($key, $value) = split(":", $_, 2);

			# Check if the current key is the one which contains the memory usage.
			# The wanted one is VmRSS which contains the Real-memory (resident set)
			# of the entire process.
			if ($key eq "VmRSS") {
				# Found the memory usage add it to the memory variable.
				$memory += $value;

				# Break the loop.
				last;
			}
		}

		# Close file handle.
		close(FILE);

		# Return memory usage.
		return $memory;
	}

	# If the file could not be open, return nothing.
	return;
}

#
## Function to read-in the given enabled or disables sids file.
#
sub read_enabled_disabled_sids_file($) {
	my ($file) = @_;

	# Temporary hash to store the sids and their state. It will be
	# returned at the end of this function.
	my %temphash;

	# Open the given filename.
	open(FILE, "$file") or die "Could not open $file. $!\n";

	# Loop through the file.
	while(<FILE>) {
		# Remove newlines.
		chomp $_;

		# Skip blank lines.
		next if ($_ =~ /^\s*$/);

		# Skip coments.
		next if ($_ =~ /^\#/);

		# Splitt line into sid and state part.
		my ($state, $sid) = split(" ", $_);

		# Skip line if the sid is not numeric.
		next unless ($sid =~ /\d+/ );

		# Check if the sid was enabled.
		if ($state eq "enablesid") {
			# Add the sid and its state as enabled to the temporary hash.
			$temphash{$sid} = "enabled";
		# Check if the sid was disabled.
		} elsif ($state eq "disablesid") {
			# Add the sid and its state as disabled to the temporary hash.
			$temphash{$sid} = "disabled";
		# Invalid state - skip the current sid and state.
		} else {
			next;
		}
	}

	# Close filehandle.
	close(FILE);

	# Return the hash.
	return %temphash;
}

#
## Private function to convert a given rulefile to a category name.
## ( No file extension anymore and if the name contained a dot, it
## would be replaced by a underline sign.)
#
sub _rulefile_to_category($) {
        my ($filename) = @_;

	# Splitt the filename into single chunks and store them in a
	# temorary array.
        my @parts = split(/\./, $filename);

	# Return / Remove last element of the temporary array.
	# This removes the file extension.
        pop @parts;

	# Join together the single elements of the temporary array.
	# If these are more than one, use a "underline" for joining.
        my $category = join '_', @parts;

	# Return the converted filename.
        return $category;
}
