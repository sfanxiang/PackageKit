#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Licensed under the GNU General Public License Version 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright (C) 2007 S.Çağlar Onur <caglar@pardus.org.tr>

import pisi
import pisi.ui
from packagekit.backend import *
from packagekit.package import PackagekitPackage
from packagekit import enums
import os.path
import piksemel

class SimplePisiHandler(pisi.ui.UI):
    
    def __init(self):
        pisi.ui.UI.__init__(self, False, False)
        
    def display_progress (self, **ka):
        self.the_callback (**ka)

class PackageKitPisiBackend(PackageKitBaseBackend, PackagekitPackage):
        
    MAPPING_FILE = "/etc/PackageKit/pisi.conf"

    def __init__(self, args):
        self._load_mapping_from_disk ()
        PackageKitBaseBackend.__init__(self, args)

        self.componentdb = pisi.db.componentdb.ComponentDB()
        self.filesdb = pisi.db.filesdb.FilesDB()
        self.installdb = pisi.db.installdb.InstallDB()
        self.packagedb = pisi.db.packagedb.PackageDB()
        self.repodb = pisi.db.repodb.RepoDB()

        # Do not ask any question to users
        self.options = pisi.config.Options()
        self.options.yes_all = True

    def _load_mapping_from_disk (self):
        """ Load the PK Group-> PiSi component mapping """
        if os.path.exists (self.MAPPING_FILE):
            with open (self.MAPPING_FILE, "r") as mapping:
                self.groups = {}
                for line in mapping.readlines():
                    line = line.replace("\r","").replace("\n","").strip()
                    if line.strip() == "" or "#" in line: continue
                    splits = line.split ("=")
                    pisi_component = splits[0].strip()
                    pk_group = splits[1].strip()
                    self.groups [pisi_component] = pk_group
        else:
            self.groups = {}
                    
    def __get_package_version(self, package):
        """ Returns version string of given package """
        # Internal FIXME: PiSi may provide this
        if package.build is not None:
            version = "%s-%s-%s" % (package.version, package.release, package.build)
        else:
            version = "%s-%s" % (package.version, package.release)
        return version

    def __get_package(self, package, filters=None):
        """ Returns package object suitable for other methods """
        if self.installdb.has_package(package):
            status = INFO_INSTALLED
            pkg = self.installdb.get_package(package)
        elif self.packagedb.has_package(package):
            status = INFO_AVAILABLE
            pkg = self.packagedb.get_package(package)
        else:
            self.error(ERROR_PACKAGE_NOT_FOUND, "Package was not found")

        if filters:
            if "none" not in filters:
                if FILTER_INSTALLED in filters and status != INFO_INSTALLED:
                    return
                if FILTER_NOT_INSTALLED in filters and status == INFO_INSTALLED:
                    return
                if FILTER_GUI in filters and "app:gui" not in pkg.isA:
                    return
                if FILTER_NOT_GUI in filters and "app:gui" in pkg.isA:
                    return

        version = self.__get_package_version(pkg)

        id = self.get_package_id(pkg.name, version, pkg.architecture, "")

        return self.package(id, status, pkg.summary)

    def get_depends(self, filters, package_ids, recursive):
        """ Prints a list of depends for a given package """
        self.allow_cancel(True)
        self.percentage(None)

        package = self.get_package_from_id(package_ids[0])[0]

        for pkg in self.packagedb.get_package(package).runtimeDependencies():
            # Internal FIXME: PiSi API has really inconsistent for return types and arguments!
            self.__get_package(pkg.package)

    def get_details(self, package_ids):
        """ Prints a detailed description for a given package """
        self.allow_cancel(True)
        self.percentage(None)

        package = self.get_package_from_id(package_ids[0])[0]

        if self.packagedb.has_package(package):
            pkg = self.packagedb.get_package(package)
            repo = self.packagedb.get_package_repo (pkg.name, None)
            pkg_id = self.get_package_id (pkg.name, self.__get_package_version(pkg), pkg.architecture, repo[1])

            if self.groups.has_key(pkg.partOf):
                group = self.groups[pkg.partOf]
            else:
                group = GROUP_UNKNOWN

            self.details(pkg_id,
                            ",".join (pkg.license),
                            group,
                            pkg.description,
                            pkg.packageURI,
                            pkg.packageSize)
        else:
            self.error(ERROR_PACKAGE_NOT_FOUND, "Package was not found")

    def get_files(self, package_ids):
        """ Prints a file list for a given package """
        self.allow_cancel(True)
        self.percentage(None)

        package = self.get_package_from_id(package_ids[0])[0]

        if self.installdb.has_package(package):
            pkg = self.packagedb.get_package(package)
            repo = self.packagedb.get_package_repo (pkg.name, None)
            pkg_id = self.get_package_id (pkg.name, self.__get_package_version(pkg), pkg.architecture, repo[1])
			
            pkg = self.installdb.get_files(package)

            files = map(lambda y: "/%s" % y.path, pkg.list)

            file_list = ";".join(files)
            self.files(pkg_id, file_list)

    def get_repo_list(self, filters):
        """ Prints available repositories """
        self.allow_cancel(True)
        self.percentage(None)

        for repo in pisi.api.list_repos():
            # Internal FIXME: What an ugly way to get repo uri
            # FIXME: Use repository enabled/disabled state
            self.repo_detail(repo, self.repodb.get_repo(repo).indexuri.get_uri(), True)

    def get_requires(self, filters, package_ids, recursive):
        """ Prints a list of requires for a given package """
        self.allow_cancel(True)
        self.percentage(None)

        package = self.get_package_from_id(package_ids[0])[0]

        # FIXME: Handle packages which is not installed from repository
        for pkg in self.packagedb.get_rev_deps(package):
            self.__get_package(pkg[0])

    def get_updates(self, filter):
        """ Prints available updates and types """
        self.allow_cancel(True)
        self.percentage(None)

        for package in pisi.api.list_upgradable():

            pkg = self.packagedb.get_package(package)

            version = self.__get_package_version(pkg)
            id = self.get_package_id(pkg.name, version, pkg.architecture, "")

            # Internal FIXME: PiSi must provide this information as a single API call :(
            updates = [i for i in self.packagedb.get_package(package).history
                    if pisi.version.Version(i.release) > pisi.version.Version(self.installdb.get_package(package).release)]
            if pisi.util.any(lambda i:i.type == "security", updates):
                self.package(id, INFO_SECURITY, pkg.summary)
            else:
                self.package(id, INFO_NORMAL, pkg.summary)

    def _extract_update_details (self, pindex, package_name):
		document = piksemel.parse (pindex)
		packages = document.tags ("Package")
		for pkg in packages:
			if pkg.getTagData ("Name") == package_name:
				history = pkg.getTag("History")
				update = history.tags ("Update")
				update_message = "Updated"
				update_release = 0
				update_data = ""
				for update in update:
					if int(update.getAttribute ("release")) > update_release:
						update_release = int(update.getAttribute ("release"))
						updater = update.getTagData ("Name")
						update_message = update.getTagData ("Comment")
						update_message = update_message.replace ("\n\n", ";").replace ("\n", " ")
						update_date = update.getTagData ("Date")
				return (update_message,update_date)
			pkg = pkg.nextTag ("Package")
		return "Great its an update."
		
    def get_update_detail(self, package_ids):
        for package_id in package_ids:
            package = self.get_package_from_id (package_id)[0]
            the_package = self.installdb.get_package (package)
            updates = [package_id]
            obsoletes = ""
            bugzilla_url = "" # TODO: Add regex matching for #FIXES:ID or something similar
            cve_url = ""
            package_url = the_package.source.homepage
            vendor_url = package_url if package_url is not None else ""
            issued = ""
            repo = self.packagedb.get_package_repo (package, None)[1]
            pindex = "/var/lib/pisi/index/%s/pisi-index.xml" % repo

            changelog = ""  
            issued = updated = "" # TODO: Set to security_issued if security update     
            update_message,security_issued = self._extract_update_details (pindex, package)
            state = UPDATE_STATE_STABLE # TODO: Add tagging to repo's, or a mapping file
            
            self.update_detail(package_id, updates, obsoletes, vendor_url,
                bugzilla_url, cve_url, "none", update_message, changelog,
                state, issued, updated)

    def download_packages(self, directory, package_ids):
        """ Download the given packages to a directory """
        self.allow_cancel (False)
        self.percentage (None)
        self.status (STATUS_DOWNLOAD)
        
        packages = list()
        
        def progress_cb (**kw):
            self.percentage (int(kw['percent']))
            
        ui = SimplePisiHandler ()
        for package_id in package_ids:
            package = self.get_package_from_id (package_id)[0]
            packages.append (package)
            try:
                pkg = self.packagedb.get_package (package)
            except:
                self.error(ERROR_PACKAGE_NOT_FOUND, "Package was not found")
        try:
            pisi.api.set_userinterface (ui)
            ui.the_callback = progress_cb
            if directory is None:
                directory = os.path.curdir
            pisi.api.fetch (packages, directory)
            # Scan for package
            for package in packages:
                package_obj = self.packagedb.get_package (package)
                uri = package_obj.packageURI.split("/")[-1]
                location = os.path.join (directory, uri)
                self.files (package_id, location)
            pisi.api.set_userinterface (None)
        except Exception, e:
            self.error(ERROR_PACKAGE_DOWNLOAD_FAILED, "Could not download package: %s" % e)
        self.percentage (None)        
            
    def install_files(self, only_trusted, files):
        """ Installs given package into system"""

        # FIXME: use only_trusted

        # FIXME: install progress
        self.allow_cancel(False)
        self.percentage(None)

        try:
            self.status(STATUS_INSTALL)
            pisi.api.install([file])
        except pisi.Error,e:
            # FIXME: Error: internal-error : Package re-install declined
            # Force needed?
            self.error(ERROR_PACKAGE_ALREADY_INSTALLED, e)

    def install_packages(self, only_trusted, package_ids):
        """ Installs given package into system"""
        # FIXME: fetch/install progress
        self.allow_cancel(False)
        self.percentage(None)

        # FIXME: use only_trusted

        package = self.get_package_from_id(package_ids[0])[0]
        
        def progress_cb (**kw):			
            self.percentage (int(kw['percent']))
            
        ui = SimplePisiHandler ()

        if self.packagedb.has_package(package):
            self.status(STATUS_INSTALL)
            pisi.api.set_userinterface (ui)
            ui.the_callback = progress_cb
            try:
                pisi.api.install([package])
            except pisi.Error,e:
                self.error(ERROR_UNKNOWN, e)
            pisi.api.set_userinterface (None)
        else:
            self.error(ERROR_PACKAGE_NOT_INSTALLED, "Package is already installed")

    def refresh_cache(self, force):
        """ Updates repository indexes """
        # TODO: use force ?
        self.allow_cancel(False)
        self.percentage(0)
        self.status(STATUS_REFRESH_CACHE)

        slice = (100/len(pisi.api.list_repos()))/2

        percentage = 0
        for repo in pisi.api.list_repos():
            pisi.api.update_repo(repo)
            percentage += slice
            self.percentage(percentage)

        self.percentage(100)

    def remove_packages(self, transaction_flags, package_ids, allowdeps, autoremove):
        """ Removes given package from system"""
        self.allow_cancel(False)
        self.percentage(None)
        # TODO: use autoremove

        def progress_cb (**kw):			
            self.percentage (int(kw['percent']))
            
        ui = SimplePisiHandler ()
        
        package = self.get_package_from_id(package_ids[0])[0]

        if self.installdb.has_package(package):
            self.status(STATUS_REMOVE)
            pisi.api.set_userinterface (ui)
            ui.the_callback = progress_cb
            try:
                pisi.api.remove([package])
            except pisi.Error,e:
                # system.base packages cannot be removed from system
                self.error(ERROR_CANNOT_REMOVE_SYSTEM_PACKAGE, e)
            pisi.api.set_userinterface (None)
        else:
            self.error(ERROR_PACKAGE_NOT_INSTALLED, "Package is not installed")

    def repo_set_data(self, repo_id, parameter, value):
        """ Sets a parameter for the repository specified """
        self.allow_cancel(False)
        self.percentage(None)

        if parameter == "add-repo":
            try:
                pisi.api.add_repo(repo_id, value, parameter)
            except pisi.Error, e:
                self.error(ERROR_UNKNOWN, e)

            try:
                pisi.api.update_repo(repo_id)
            except pisi.fetcher.FetchError:
                pisi.api.remove_repo(repo_id)
                self.error(ERROR_REPO_NOT_FOUND, "Could not be reached to repository, removing from system")
        elif parameter == "remove-repo":
            try:
                pisi.api.remove_repo(repo_id)
            except pisi.Error:
                self.error(ERROR_REPO_NOT_FOUND, "Repository is not exists")
        else:
            self.error(ERROR_NOT_SUPPORTED, "Parameter not supported")

    def resolve(self, filters, package):
        """ Turns a single package name into a package_id suitable for the other methods """
        self.allow_cancel(True)
        self.percentage(None)

        self.__get_package(package[0], filters)

    def search_details(self, filters, values):
        """ Prints a detailed list of packages contains search term """
        self.allow_cancel(True)
        self.percentage(None)
        self.status(STATUS_INFO)

        # Internal FIXME: Use search_details instead of _package when API gains that ability :)
        for pkg in pisi.api.search_package(values):
            self.__get_package(pkg, filters)

    def search_file(self, filters, values):
        """ Prints the installed package which contains the specified file """
        self.allow_cancel(True)
        self.percentage(None)
        self.status(STATUS_INFO)

        for value in values:
            # Internal FIXME: Why it is needed?
            value = value.lstrip("/")

            for pkg, files in pisi.api.search_file(value):
                self.__get_package(pkg)

    def search_group(self, filters, values):
        """ Prints a list of packages belongs to searched group """
        self.allow_cancel(True)
        self.percentage(None)
        self.status(STATUS_INFO)

        for value in values:
			packages = list()
			for item in self.groups:
				if self.groups[item] == value:		
					try:
						packages.extend (self.componentdb.get_packages(item, walk=False))
					except:
						self.error(ERROR_GROUP_NOT_FOUND,
								   "Component %s was not found" % value)
			for pkg in packages:
				self.__get_package(pkg, filters)

    def search_name(self, filters, values):
        """ Prints a list of packages contains search term in its name """
        self.allow_cancel(True)
        self.percentage(None)
        self.status(STATUS_INFO)

        for value in values:
            for pkg in pisi.api.search_package([value]):
                self.__get_package(pkg, filters)

    def update_packages(self, only_trusted, package_ids):
        """ Updates given package to its latest version """

        # FIXME: use only_trusted

        # FIXME: fetch/install progress
        self.allow_cancel(False)
        self.percentage(None)

        package = self.get_package_from_id(package_ids[0])[0]

        if self.installdb.has_package(package):
            try:
                pisi.api.upgrade([package])
            except pisi.Error,e:
                self.error(ERROR_UNKNOWN, e)
        else:
            self.error(ERROR_PACKAGE_NOT_INSTALLED, "Package is already installed")

    def update_system(self, only_trusted):
        """ Updates all available packages """

        # FIXME: use only_trusted

        # FIXME: fetch/install progress
        self.allow_cancel(False)
        self.percentage(None)

        if not len(pisi.api.list_upgradable()) > 0:
            self.error(ERROR_NO_PACKAGES_TO_UPDATE, "System is already up2date")

        try:
            pisi.api.upgrade(pisi.api.list_upgradable())
        except pisi.Error,e:
            self.error(ERROR_UNKNOWN, e)

def main():
    backend = PackageKitPisiBackend('')
    backend.dispatcher(sys.argv[1:])

if __name__ == "__main__":
    main()

