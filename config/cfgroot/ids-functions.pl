#!/usr/bin/perl -w
############################################################################
#                                                                          #
# This file is part of the IPFire Firewall.                                #
#                                                                          #
# IPFire is free software; you can redistribute it and/or modify           #
# it under the terms of the GNU General Public License as published by     #
# the Free Software Foundation; either version 2 of the License, or        #
# (at your option) any later version.                                      #
#                                                                          #
# IPFire is distributed in the hope that it will be useful,                #
# but WITHOUT ANY WARRANTY; without even the implied warranty of           #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
# GNU General Public License for more details.                             #
#                                                                          #
# You should have received a copy of the GNU General Public License        #
# along with IPFire; if not, write to the Free Software                    #
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA #
#                                                                          #
# Copyright (C) 2018-2019 IPFire Team <info@ipfire.org>                    #
#                                                                          #
############################################################################

package IDS;

require '/var/ipfire/general-functions.pl';

# Location where all config and settings files are stored.
our $settingsdir = "${General::swroot}/suricata";

# File where the used rulefiles are stored.
our $used_rulefiles_file = "$settingsdir/suricata-used-rulefiles.yaml";

# File where the addresses of the homenet are stored.
our $homenet_file = "$settingsdir/suricata-homenet.yaml";

# File where the addresses of the used DNS servers are stored.
our $dns_servers_file = "$settingsdir/suricata-dns-servers.yaml";

# File where the HTTP ports definition is stored.
our $http_ports_file = "$settingsdir/suricata-http-ports.yaml";

# File which contains the enabled sids.
our $enabled_sids_file = "$settingsdir/oinkmaster-enabled-sids.conf";

# File which contains the disabled sids.
our $disabled_sids_file = "$settingsdir/oinkmaster-disabled-sids.conf";

# File which contains wheater the rules should be changed.
our $modify_sids_file = "$settingsdir/oinkmaster-modify-sids.conf";

# File which stores the configured IPS settings.
our $ids_settings_file = "$settingsdir/settings";

# File which stores the configured rules-settings.
our $rules_settings_file = "$settingsdir/rules-settings";

# File which stores the configured settings for whitelisted addresses.
our $ignored_file = "$settingsdir/ignored";

# Location and name of the tarball which contains the ruleset.
our $rulestarball = "/var/tmp/idsrules.tar.gz";

# File to store any errors, which also will be read and displayed by the wui.
our $storederrorfile = "/tmp/ids_storederror";

# File to lock the WUI, while the autoupdate script runs.
our $ids_page_lock_file = "/tmp/ids_page_locked";

# Location where the rulefiles are stored.
our $rulespath = "/var/lib/suricata";

# Location to store local rules. This file will not be touched.
our $local_rules_file = "$rulespath/local.rules";

# File which contains the rules to whitelist addresses on suricata.
our $whitelist_file = "$rulespath/whitelist.rules";

# File which contains a list of all supported ruleset sources.
# (Sourcefire, Emergingthreads, etc..)
our $rulesetsourcesfile = "$settingsdir/ruleset-sources";

# The pidfile of the IDS.
our $idspidfile = "/var/run/suricata.pid";

# Location of suricatactrl.
my $suricatactrl = "/usr/local/bin/suricatactrl";

# Array with allowed commands of suricatactrl.
my @suricatactrl_cmds = ( 'start', 'stop', 'restart', 'reload', 'fix-rules-dir', 'cron' );

# Array with supported cron intervals.
my @cron_intervals = ('off', 'daily', 'weekly' );

# Array which contains the HTTP ports, which statically will be declared as HTTP_PORTS in the
# http_ports_file.
my @http_ports = ('80', '81');

#
## Function to check and create all IDS related files, if the does not exist.
#
sub check_and_create_filelayout() {
	# Check if the files exist and if not, create them.
	unless (-f "$enabled_sids_file") { &create_empty_file($enabled_sids_file); }
	unless (-f "$disabled_sids_file") { &create_empty_file($disabled_sids_file); }
	unless (-f "$modify_sids_file") { &create_empty_file($modify_sids_file); }
	unless (-f "$used_rulefiles_file") { &create_empty_file($used_rulefiles_file); }
	unless (-f "$ids_settings_file") { &create_empty_file($ids_settings_file); }
	unless (-f "$rules_settings_file") { &create_empty_file($rules_settings_file); }
	unless (-f "$ignored_file") { &create_empty_file($ignored_file); }
	unless (-f "$whitelist_file" ) { &create_empty_file($whitelist_file); }
}

#
## Function for checking if at least 300MB of free disk space are available
## on the "/var" partition.
#
sub checkdiskspace () {
	# Call diskfree to gather the free disk space of /var.
	my @df = `/bin/df -B M /var`;

	# Loop through the output.
	foreach my $line (@df) {
		# Ignore header line.
		next if $line =~ m/^Filesystem/;

		# Search for a line with the device information.
		if ($line =~ m/dev/ ) {
			# Split the line into single pieces.
			my @values = split(' ', $line);
			my ($filesystem, $blocks, $used, $available, $used_perenctage, $mounted_on) = @values;

			# Check if the available disk space is more than 300MB.
			if ($available < 300) {
				# Log error to syslog.
				&_log_to_syslog("Not enough free disk space on /var. Only $available MB from 300 MB available.");

				# Exit function and return "1" - False.
				return 1;
			}
		}
	}

	# Everything okay, return nothing.
	return;
}

#
## This function is responsible for downloading the configured IDS ruleset.
##
## * At first it obtains from the stored rules settings which ruleset should be downloaded.
## * The next step is to get the download locations for all available rulesets.
## * After that, the function will check if an upstream proxy should be used and grab the settings.
## * The last step will be to generate the final download url, by obtaining the URL for the desired
##   ruleset, add the settings for the upstream proxy and final grab the rules tarball from the server.
#
sub downloadruleset {
	# Get rules settings.
	my %rulessettings=();
	&General::readhash("$rules_settings_file", \%rulessettings);

	# Check if a ruleset has been configured.
	unless($rulessettings{'RULES'}) {
		# Log that no ruleset has been configured and abort.
		&_log_to_syslog("No ruleset source has been configured.");

		# Return "1".
		return 1;
	}

	# Get all available ruleset locations.
	my %rulesetsources=();
	&General::readhash($rulesetsourcesfile, \%rulesetsources);

	# Read proxysettings.
	my %proxysettings=();
	&General::readhash("${General::swroot}/proxy/settings", \%proxysettings);

	# Load required perl module to handle the download.
	use LWP::UserAgent;

	# Init the download module.
	my $downloader = LWP::UserAgent->new;

	# Set timeout to 10 seconds.
	$downloader->timeout(10);

	# Check if an upstream proxy is configured.
	if ($proxysettings{'UPSTREAM_PROXY'}) {
		my $proxy_url;

		$proxy_url = "http://";

		# Check if the proxy requires authentication.
		if (($proxysettings{'UPSTREAM_USER'}) && ($proxysettings{'UPSTREAM_PASSWORD'})) {
			$proxy_url .= "$proxysettings{'UPSTREAM_USER'}\:$proxysettings{'UPSTREAM_PASSWORD'}\@";
		}

		# Add proxy server address and port.
		$proxy_url .= $proxysettings{'UPSTREAM_PROXY'};

		# Setup proxy settings.
		$downloader->proxy(['http', 'https'], $proxy_url);
	}

	# Grab the right url based on the configured vendor.
	my $url = $rulesetsources{$rulessettings{'RULES'}};

	# Check if the vendor requires an oinkcode and add it if needed.
	$url =~ s/\<oinkcode\>/$rulessettings{'OINKCODE'}/g;

	# Abort if no url could be determined for the vendor.
	unless ($url) {
		# Log error and abort.
		&_log_to_syslog("Unable to gather a download URL for the selected ruleset.");
		return 1;
	}

	# Variable to store the filesize of the remote object.
	my $remote_filesize;

	# The sourcfire (snort rules) does not allow to send "HEAD" requests, so skip this check
	# for this webserver.
	#
	# Check if the ruleset source contains "snort.org".
	unless ($url =~ /\.snort\.org/) {
		# Pass the requrested url to the downloader.
		my $request = HTTP::Request->new(HEAD => $url);

		# Accept the html header.
		$request->header('Accept' => 'text/html');

		# Perform the request and fetch the html header.
		my $response = $downloader->request($request);

		# Check if there was any error.
		unless ($response->is_success) {
			# Obtain error.
			my $error = $response->status_line();

			# Log error message.
			&_log_to_syslog("Unable to download the ruleset. \($error\)");

			# Return "1" - false.
			return 1;
		}

		# Assign the fetched header object.
		my $header = $response->headers();

		# Grab the remote file size from the object and store it in the
		# variable.
		$remote_filesize = $header->content_length;
	}

	# Load perl module to deal with temporary files.
	use File::Temp;

	# Generate temporary file name, located in "/var/tmp" and with a suffix of ".tar.gz".
	my $tmp = File::Temp->new( SUFFIX => ".tar.gz", DIR => "/var/tmp/", UNLINK => 0 );
	my $tmpfile = $tmp->filename();

	# Pass the requested url to the downloader.
	my $request = HTTP::Request->new(GET => $url);

	# Perform the request and save the output into the tmpfile.
	my $response = $downloader->request($request, $tmpfile);

	# Check if there was any error.
	unless ($response->is_success) {
		# Obtain error.
		my $error = $response->content;

		# Log error message.
		&_log_to_syslog("Unable to download the ruleset. \($error\)");

		# Return "1" - false.
		return 1;
	}

	# Load perl stat module.
	use File::stat;

	# Perform stat on the tmpfile.
	my $stat = stat($tmpfile);

	# Grab the local filesize of the downloaded tarball.
	my $local_filesize = $stat->size;

	# Check if both file sizes match.
	if (($remote_filesize) && ($remote_filesize ne $local_filesize)) {
		# Log error message.
		&_log_to_syslog("Unable to completely download the ruleset. ");
		&_log_to_syslog("Only got $local_filesize Bytes instead of $remote_filesize Bytes. ");

		# Delete temporary file.
		unlink("$tmpfile");

		# Return "1" - false.
		return 1;
	}

	# Load file copy module, which contains the move() function.
	use File::Copy;

	# Overwrite existing rules tarball with the new downloaded one.
	move("$tmpfile", "$rulestarball");

	# Set correct ownership for the rulesdir and files.
	set_ownership("$rulestarball");

	# If we got here, everything worked fine. Return nothing.
	return;
}

#
## A tiny wrapper function to call the oinkmaster script.
#
sub oinkmaster () {
	# Check if the files in rulesdir have the correct permissions.
	&_check_rulesdir_permissions();

	# Cleanup the rules directory before filling it with the new rulest.
	&_cleanup_rulesdir();

	# Load perl module to talk to the kernel syslog.
	use Sys::Syslog qw(:DEFAULT setlogsock);

	# Establish the connection to the syslog service.
	openlog('oinkmaster', 'cons,pid', 'user');

	# Call oinkmaster to generate ruleset.
	open(OINKMASTER, "/usr/local/bin/oinkmaster.pl -s -u file://$rulestarball -C $settingsdir/oinkmaster.conf -o $rulespath 2>&1 |") or die "Could not execute oinkmaster $!\n";

	# Log output of oinkmaster to syslog.
	while(<OINKMASTER>) {
		# The syslog function works best with an array based input,
		# so generate one before passing the message details to syslog.
		my @syslog = ("INFO", "$_");

		# Send the log message.
		syslog(@syslog);
	}

	# Close the pipe to oinkmaster process.
	close(OINKMASTER);

	# Close the log handle.
	closelog();
}

#
## Function to do all the logging stuff if the downloading or updating of the ruleset fails.
#
sub log_error ($) {
	my ($error) = @_;

	# Remove any newline.
	chomp($error);

	# Call private function to log the error message to syslog.
	&_log_to_syslog($error);

	# Call private function to write/store the error message in the storederrorfile.
	&_store_error_message($error);
}

#
## Function to log a given error message to the kernel syslog.
#
sub _log_to_syslog ($) {
	my ($message) = @_;

	# Load perl module to talk to the kernel syslog.
	use Sys::Syslog qw(:DEFAULT setlogsock);

	# The syslog function works best with an array based input,
	# so generate one before passing the message details to syslog.
	my @syslog = ("ERR", "<ERROR> $message");

	# Establish the connection to the syslog service.
	openlog('oinkmaster', 'cons,pid', 'user');

	# Send the log message.
	syslog(@syslog);

	# Close the log handle.
	closelog();
}

#
## Private function to write a given error message to the storederror file.
#
sub _store_error_message ($) {
        my ($message) = @_;

	# Remove any newline.
	chomp($message);

        # Open file for writing.
        open (ERRORFILE, ">$storederrorfile") or die "Could not write to $storederrorfile. $!\n";

        # Write error to file.
        print ERRORFILE "$message\n";

        # Close file.
        close (ERRORFILE);

	# Set correct ownership for the file.
	&set_ownership("$storederrorfile");
}

#
## Function to get a list of all available network zones.
#
sub get_available_network_zones () {
	# Get netsettings.
	my %netsettings = ();
	&General::readhash("${General::swroot}/ethernet/settings", \%netsettings);

	# Obtain the configuration type from the netsettings hash.
	my $config_type = $netsettings{'CONFIG_TYPE'};

	# Hash which contains the conversation from the config mode
	# to the existing network interface names. They are stored like
	# an array.
	#
	# Mode "0" red is a modem and green
	# Mode "1" red is a netdev and green
	# Mode "2" red, green and orange
	# Mode "3" red, green and blue
	# Mode "4" red, green, blue, orange
	my %config_type_to_interfaces = (
		"0" => [ "red", "green" ],
		"1" => [ "red", "green" ],
		"2" => [ "red", "green", "orange" ],
		"3" => [ "red", "green", "blue" ],
		"4" => [ "red", "green", "blue", "orange" ]
	);

	# Obtain and dereference the corresponding network interaces based on the read
	# network config type.
	my @network_zones = @{ $config_type_to_interfaces{$config_type} };

	# Return them.
	return @network_zones;
}

#
## Function to check if the IDS is running.
#
sub ids_is_running () {
	if(-f $idspidfile) {
		# Open PID file for reading.
		open(PIDFILE, "$idspidfile") or die "Could not open $idspidfile. $!\n";

		# Grab the process-id.
		my $pid = <PIDFILE>;

		# Close filehandle.
		close(PIDFILE);

		# Remove any newline.
		chomp($pid);

		# Check if a directory for the process-id exists in proc.
		if(-d "/proc/$pid") {
			# The IDS daemon is running return the process id.
			return $pid;
		}
	}

	# Return nothing - IDS is not running.
	return;
}

#
## Function to call suricatactrl binary with a given command.
#
sub call_suricatactrl ($) {
	# Get called option.
	my ($option, $interval) = @_;

	# Loop through the array of supported commands and check if
	# the given one is part of it.
	foreach my $cmd (@suricatactrl_cmds) {
		# Skip current command unless the given one has been found.
		next unless($cmd eq $option);

		# Check if the given command is "cron".
		if ($option eq "cron") {
			# Check if an interval has been given.
			if ($interval) {
				# Check if the given interval is valid.
				foreach my $element (@cron_intervals) {
					# Skip current element until the given one has been found.
					next unless($element eq $interval);

					# Call the suricatactrl binary and pass the "cron" command
					# with the requrested interval.
					system("$suricatactrl $option $interval &>/dev/null");

					# Return "1" - True.
					return 1;
				}
			}

			# If we got here, the given interval is not supported or none has been given. - Return nothing.
			return;
		} else {
			# Call the suricatactrl binary and pass the requrested
			# option to it.
			system("$suricatactrl $option &>/dev/null");

			# Return "1" - True.
			return 1;
		}
	}

	# Command not found - return nothing.
	return;
}

#
## Function to create a new empty file.
#
sub create_empty_file($) {
	my ($file) = @_;

	# Check if the given file exists.
	if(-e $file) {
		# Do nothing to prevent from overwriting existing files.
		return;
	}

	# Open the file for writing.
	open(FILE, ">$file") or die "Could not write to $file. $!\n";

	# Close file handle.
	close(FILE);

	# Return true.
	return 1;
}

#
## Private function to check if the file permission of the rulespath are correct.
## If not, call suricatactrl to fix them.
#
sub _check_rulesdir_permissions() {
	# Check if the rulepath main directory is writable.
	unless (-W $rulespath) {
		# If not call suricatctrl to fix it.
		&call_suricatactrl("fix-rules-dir");
	}

	# Open snort rules directory and do a directory listing.
	opendir(DIR, $rulespath) or die $!;
	# Loop through the direcory.
	while (my $file = readdir(DIR)) {
		# We only want files.
		next unless (-f "$rulespath/$file");

		# Check if the file is writable by the user.
		if (-W "$rulespath/$file") {
			# Everything is okay - go on to the next file.
			next;
		} else {
			# There are wrong permissions, call suricatactrl to fix it.
			&call_suricatactrl("fix-rules-dir");
		}
	}
}

#
## Private function to cleanup the directory which contains
## the IDS rules, before extracting and modifing the new ruleset.
#
sub _cleanup_rulesdir() {
	# Open rules directory and do a directory listing.
	opendir(DIR, $rulespath) or die $!;

	# Loop through the direcory.
	while (my $file = readdir(DIR)) {
		# We only want files.
		next unless (-f "$rulespath/$file");

		# Skip element if it has config as file extension.
		next if ($file =~ m/\.config$/);

		# Skip rules file for whitelisted hosts.
		next if ("$rulespath/$file" eq $whitelist_file);

		# Skip rules file with local rules.
		next if ("$rulespath/$file" eq $local_rules_file);

		# Delete the current processed file, if not, exit this function
		# and return an error message.
		unlink("$rulespath/$file") or return "Could not delete $rulespath/$file. $!\n";
	}

	# Return nothing;
	return;
}

#
## Function to generate the file which contains the home net information.
#
sub generate_home_net_file() {
	my %netsettings;

	# Read-in network settings.
	&General::readhash("${General::swroot}/ethernet/settings", \%netsettings);

	# Get available network zones.
	my @network_zones = &get_available_network_zones();

	# Temporary array to store network address and prefix of the configured
	# networks.
	my @networks;

	# Loop through the array of available network zones.
	foreach my $zone (@network_zones) {
		# Check if the current processed zone is red.
		if($zone eq "red") {
			# Grab the IP-address of the red interface.
			my $red_address = &get_red_address();

			# Check if an address has been obtained.
			if ($red_address) {
				# Generate full network string.
				my $red_network = join("/", $red_address, "32");

				# Add the red network to the array of networks.
				push(@networks, $red_network);
			}

			# Check if the configured RED_TYPE is static.
			if ($netsettings{'RED_TYPE'} eq "STATIC") {
				# Get configured and enabled aliases.
				my @aliases = &get_aliases();

				# Loop through the array.
				foreach my $alias (@aliases) {
					# Add "/32" prefix.
					my $network = join("/", $alias, "32");

					# Add the generated network to the array of networks.
					push(@networks, $network);
				}
			}
		# Process remaining network zones.
		} else {
			# Convert current zone name into upper case.
			$zone = uc($zone);

			# Generate key to access the required data from the netsettings hash.
			my $zone_netaddress = $zone . "_NETADDRESS";
			my $zone_netmask = $zone . "_NETMASK";

			# Obtain the settings from the netsettings hash.
			my $netaddress = $netsettings{$zone_netaddress};
			my $netmask = $netsettings{$zone_netmask};

			# Convert the subnetmask into prefix notation.
			my $prefix = &Network::convert_netmask2prefix($netmask);

			# Generate full network string.
			my $network = join("/", $netaddress,$prefix);

			# Check if the network is valid.
			if(&Network::check_subnet($network)) {
				# Add the generated network to the array of networks.
				push(@networks, $network);
			}
		}
	}

	# Format home net declaration.
	my $line = "\"[" . join(',', @networks) . "]\"";

	# Open file to store the addresses of the home net.
	open(FILE, ">$homenet_file") or die "Could not open $homenet_file. $!\n";

	# Print yaml header.
	print FILE "%YAML 1.1\n";
	print FILE "---\n\n";

	# Print notice about autogenerated file.
	print FILE "#Autogenerated file. Any custom changes will be overwritten!\n";

	# Print the generated and required HOME_NET declaration to the file.
	print FILE "HOME_NET:\t$line\n";

	# Close file handle.
	close(FILE);
}

#
# Function to generate and write the file which contains the configured and used DNS servers.
#
sub generate_dns_servers_file() {
	# Get the used DNS servers.
	my @nameservers = &General::get_nameservers();

	# Get network settings.
	my %netsettings;
	&General::readhash("${General::swroot}/ethernet/settings", \%netsettings);

	# Format dns servers declaration.
	my $line = "";

	# Check if the system has configured nameservers.
	if (@nameservers) {
		# Add the GREEN address as DNS servers.
		push(@nameservers, $netsettings{'GREEN_ADDRESS'});

		# Check if a BLUE zone exists.
		if ($netsettings{'BLUE_ADDRESS'}) {
			# Add the BLUE address to the array of nameservers.
			push(@nameservers, $netsettings{'BLUE_ADDRESS'});
		}

		# Generate the line which will be written to the DNS servers file.
		$line = join(",", @nameservers);
	} else {
		# External net simply contains (any).
		$line = "\$EXTERNAL_NET";
	}

	# Open file to store the used DNS server addresses.
	open(FILE, ">$dns_servers_file") or die "Could not open $dns_servers_file. $!\n";

	# Print yaml header.
	print FILE "%YAML 1.1\n";
	print FILE "---\n\n";

	# Print notice about autogenerated file.
	print FILE "#Autogenerated file. Any custom changes will be overwritten!\n";

	# Print the generated DNS declaration to the file.
	print FILE "DNS_SERVERS:\t\"[$line]\"\n";

	# Close file handle.
	close(FILE);
}

#
# Function to generate and write the file which contains the HTTP_PORTS definition.
#
sub generate_http_ports_file() {
	my %proxysettings;

	# Read-in proxy settings
	&General::readhash("${General::swroot}/proxy/advanced/settings", \%proxysettings);

	# Check if the proxy is enabled.
	if (( -e "${General::swroot}/proxy/enable") || (-e "${General::swroot}/proxy/enable_blue")) {
		# Add the proxy port to the array of HTTP ports.
		push(@http_ports, $proxysettings{'PROXY_PORT'});
	}

	# Check if the transparent mode of the proxy is enabled.
	if ((-e "${General::swroot}/proxy/transparent") || (-e "${General::swroot}/proxy/transparent_blue")) {
		# Add the transparent proxy port to the array of HTTP ports.
		push(@http_ports, $proxysettings{'TRANSPARENT_PORT'});
	}

	# Format HTTP_PORTS declaration.
	my $line = "";

	# Generate line which will be written to the http ports file.
	$line = join(",", @http_ports);

	# Open file to store the HTTP_PORTS.
	open(FILE, ">$http_ports_file") or die "Could not open $http_ports_file. $!\n";

	# Print yaml header.
	print FILE "%YAML 1.1\n";
	print FILE "---\n\n";

	# Print notice about autogenerated file.
	print FILE "#Autogenerated file. Any custom changes will be overwritten!\n";

	# Print the generated HTTP_PORTS declaration to the file.
	print FILE "HTTP_PORTS:\t\"[$line]\"\n";

	# Close file handle.
	close(FILE);
}

#
## Function to generate and write the file for used rulefiles.
#
sub write_used_rulefiles_file(@) {
	my @files = @_;

	# Open file for used rulefiles.
	open (FILE, ">$used_rulefiles_file") or die "Could not write to $used_rulefiles_file. $!\n";

	# Write yaml header to the file.
	print FILE "%YAML 1.1\n";
	print FILE "---\n\n";

	# Write header to file.
	print FILE "#Autogenerated file. Any custom changes will be overwritten!\n";

	# Allways use the whitelist.
	print FILE " - whitelist.rules\n";

	# Loop through the array of given files.
	foreach my $file (@files) {
		# Check if the given filename exists and write it to the file of used rulefiles.
		if(-f "$rulespath/$file") {
			print FILE " - $file\n";
		}
	}

	# Close file after writing.
	close(FILE);
}

#
## Function to generate and write the file for modify the ruleset.
#
sub write_modify_sids_file() {
	# Get configured settings.
	my %idssettings=();
	my %rulessettings=();
	&General::readhash("$ids_settings_file", \%idssettings);
	&General::readhash("$rules_settings_file", \%rulessettings);

	# Gather the configured ruleset.
	my $ruleset = $rulessettings{'RULES'};

	# Open modify sid's file for writing.
	open(FILE, ">$modify_sids_file") or die "Could not write to $modify_sids_file. $!\n";

	# Write file header.
	print FILE "#Autogenerated file. Any custom changes will be overwritten!\n";

	# Check if the traffic only should be monitored.
	unless($idssettings{'MONITOR_TRAFFIC_ONLY'} eq 'on') {
		# Suricata is in IPS mode, which means that the rule actions have to be changed
		# from 'alert' to 'drop', however not all rules should be changed.  Some rules
		# exist purely to set a flowbit which is used to convey other information, such
		# as a specific type of file being downloaded, to other rulewhich then check for
		# malware in that file.  Rules which fall into the first category should stay as
		# alert since not all flows of that type contain malware.

		if($ruleset eq 'registered' or $ruleset eq 'subscripted' or $ruleset eq 'community') {
			# These types of rulesfiles contain meta-data which gives the action that should
			# be used when in IPS mode.  Do the following:
			#
			# 1. Disable all rules and set the action to 'drop'
			# 2. Set the action back to 'alert' if the rule contains 'flowbits:noalert;'
			#    This should give rules not in the policy a reasonable default if the user
			#    manually enables them.
			# 3. Enable rules and set actions according to the meta-data strings.

			my $policy = 'balanced';  # Placeholder to allow policy to be changed.

			print FILE <<END;
modifysid * "^#?(?:alert|drop)" | "#drop"
modifysid * "^#drop(.+flowbits:noalert;)" | "#alert\${1}"
modifysid * "^#(?:alert|drop)(.+policy $policy-ips alert)" | "alert\${1}"
modifysid * "^#(?:alert|drop)(.+policy $policy-ips drop)" | "drop\${1}"
END
		} else {
			# These rulefiles don't have the metadata, so set rules to 'drop' unless they
			# contain the string 'flowbits:noalert;'.
			print FILE <<END;
modifysid * "^(#?)(?:alert|drop)" | "\${1}drop"
modifysid * "^(#?)drop(.+flowbits:noalert;)" | "\${1}alert\${2}"
END
		}
	}

	# Close file handle.
	close(FILE);
}

#
## Function to gather the version of suricata.
#
sub get_suricata_version($) {
	my ($format) = @_;

	# Execute piped suricata command and return the version information.
	open(SURICATA, "suricata -V |") or die "Couldn't execute program: $!";

	# Grab and store the output of the piped program.
	my $version_string = <SURICATA>;

	# Close pipe.
        close(SURICATA);

	# Remove newlines.
        chomp($version_string);

	# Grab the version from the version string.
	$version_string =~ /([0-9]+([.][0-9]+)+)/;

	# Splitt the version into single chunks.
	my ($major_ver, $minor_ver, $patchlevel) = split(/\./, $1);

	# Check and return the requested version sheme.
	if ($format eq "major") {
		# Return the full version.
		return "$major_ver";
	} elsif ($format eq "minor") {
		# Return the major and minor part.
		return "$major_ver.$minor_ver";
	} else {
		# Return the full version string.
		return "$major_ver.$minor_ver.$patchlevel";
	}
}

#
## Function to generate the rules file with whitelisted addresses.
#
sub generate_ignore_file() {
	my %ignored = ();

	# SID range 1000000-1999999 Reserved for Local Use
	# Put your custom rules in this range to avoid conflicts
	my $sid = 1500000;

	# Read-in ignoredfile.
	&General::readhasharray($IDS::ignored_file, \%ignored);

	# Open ignorefile for writing.
	open(FILE, ">$IDS::whitelist_file") or die "Could not write to $IDS::whitelist_file. $!\n";

	# Config file header.
	print FILE "# Autogenerated file.\n";
	print FILE "# All user modifications will be overwritten.\n\n";

	# Add all user defined addresses to the whitelist.
	#
	# Check if the hash contains any elements.
	if (keys (%ignored)) {
		# Loop through the entire hash and write the host/network
		# and remark to the ignore file.
		while ( (my $key) = each %ignored) {
			my $address = $ignored{$key}[0];
			my $remark = $ignored{$key}[1];
			my $status = $ignored{$key}[2];

			# Check if the status of the entry is "enabled".
			if ($status eq "enabled") {
				# Check if the address/network is valid.
				if ((&General::validip($address)) || (&General::validipandmask($address))) {
					# Write rule line to the file to pass any traffic from this IP
					print FILE "pass ip $address any -> any any (msg:\"pass all traffic from/to $address\"\; sid:$sid\;)\n";

					# Increment sid.
					$sid++;
				}
			}
		}
	}

	close(FILE);
}

#
## Function to set correct ownership for single files and directories.
#

sub set_ownership($) {
	my ($target) = @_;

	# User and group of the WUI.
	my $uname = "nobody";
	my $grname = "nobody";

	# The chown function implemented in perl requies the user and group as nummeric id's.
	my $uid = getpwnam($uname);
	my $gid = getgrnam($grname);

	# Check if the given target exists.
	unless ($target) {
		# Stop the script and print error message.
		die "The $target does not exist. Cannot change the ownership!\n";
	}

	# Check weather the target is a file or directory.
	if (-f $target) {
		# Change ownership ot the single file.
		chown($uid, $gid, "$target");
	} elsif (-d $target) {
		# Do a directory listing.
		opendir(DIR, $target) or die $!;
			# Loop through the direcory.
			while (my $file = readdir(DIR)) {

				# We only want files.
				next unless (-f "$target/$file");

				# Set correct ownership for the files.
				chown($uid, $gid, "$target/$file");
			}

		closedir(DIR);

		# Change ownership of the directory.
		chown($uid, $gid, "$target");
	}
}

#
## Function to read-in the aliases file and returns all configured and enabled aliases.
#
sub get_aliases() {
	# Location of the aliases file.
	my $aliases_file = "${General::swroot}/ethernet/aliases";

	# Array to store the aliases.
	my @aliases;

	# Check if the file is empty.
	if (-z $aliases_file) {
		# Abort nothing to do.
		return;
	}

	# Open the aliases file.
	open(ALIASES, $aliases_file) or die "Could not open $aliases_file. $!\n";

	# Loop through the file content.
	while (my $line = <ALIASES>) {
		# Remove newlines.
		chomp($line);

		# Splitt line content into single chunks.
		my ($address, $state, $remark) = split(/\,/, $line);

		# Check if the state of the current processed alias is "on".
		if ($state eq "on") {
			# Check if the address is valid.
			if(&Network::check_ip_address($address)) {
				# Add the alias to the array of aliases.
				push(@aliases, $address);
			}
		}
	}

	# Close file handle.
	close(ALIASES);

	# Return the array.
	return @aliases;
}

#
## Function to grab the current assigned IP-address on red.
#
sub get_red_address() {
	# File, which contains the current IP-address of the red interface.
	my $file = "${General::swroot}/red/local-ipaddress";

	# Check if the file exists.
	if (-e $file) {
		# Open the given file.
		open(FILE, "$file") or die "Could not open $file.";

		# Obtain the address from the first line of the file.
		my $address = <FILE>;

		# Close filehandle
		close(FILE);

		# Remove newlines.
		chomp $address;

		# Check if the grabbed address is valid.
		if (&General::validip($address)) {
			# Return the address.
			return $address;
		}
	}

	# Return nothing.
	return;
}

#
## Function to write the lock file for locking the WUI, while
## the autoupdate script runs.
#
sub lock_ids_page() {
	# Call subfunction to create the file.
	&create_empty_file($ids_page_lock_file);
}

#
## Function to release the lock of the WUI, again.
#
sub unlock_ids_page() {
	# Delete lock file.
	unlink($ids_page_lock_file);
}

1;
