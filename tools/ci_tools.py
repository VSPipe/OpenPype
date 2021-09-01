import re
import sys
from semver import VersionInfo
from git import Repo
from optparse import OptionParser


def remove_prefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]


def get_last_version(match):
    repo = Repo()
    assert not repo.bare
    version_types = {
        "CI": "CI/[0-9]*",
        "release": "[0-9]*"
    }
    tag = repo.git.describe(
        '--tags',
        f'--match={version_types[match]}',
        '--abbrev=0'
        )

    if match == "CI":
        return remove_prefix(tag, "CI/"), tag
    else:
        return tag, tag


def get_log_since_tag(version):
    repo = Repo()
    assert not repo.bare
    return repo.git.log(f'{version}..HEAD', '--merges', '--oneline')


def release_type(log):
    regex_minor = ["feature/", "(feat)"]
    regex_patch = ["bugfix/", "fix/", "(fix)", "enhancement/"]
    for reg in regex_minor:
        if re.search(reg, log):
            return "minor"
    for reg in regex_patch:
        if re.search(reg, log):
            return "patch"
    return None


def file_regex_replace(filename, regex, version):
    with open(filename, 'r+') as f:
        text = f.read()
        text = re.sub(regex, version, text)
        # pp.pprint(f"NEW VERSION {version} INSERTED into {filename}")
        f.seek(0)
        f.write(text)
        f.truncate()


def bump_file_versions(version):

    filename = "./openpype/version.py"
    regex = "(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?"
    file_regex_replace(filename, regex, version)

    # bump pyproject.toml
    filename = "pyproject.toml"
    regex = "version = \"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?\" # OpenPype"
    pyproject_version = f"version = \"{version}\" # OpenPype"
    file_regex_replace(filename, regex, pyproject_version)


def calculate_next_nightly(token="nightly"):
    last_prerelease, last_pre_tag = get_last_version("CI")
    last_pre_v = VersionInfo.parse(last_prerelease)
    last_pre_v_finalized = last_pre_v.finalize_version()
    # print(last_pre_v_finalized)

    last_release, last_release_tag = get_last_version("release")

    last_release_v = VersionInfo.parse(last_release)
    bump_type = release_type(get_log_since_tag(last_release))
    if not bump_type:
        return None

    next_release_v = last_release_v.next_version(part=bump_type)
    # print(next_release_v)

    if next_release_v > last_pre_v_finalized:
        next_tag = next_release_v.bump_prerelease(token=token).__str__()
        return next_tag
    elif next_release_v == last_pre_v_finalized:
        next_tag = last_pre_v.bump_prerelease(token=token).__str__()
        return next_tag

def finalize_latest_nightly():
    last_prerelease, last_pre_tag = get_last_version("CI")
    last_pre_v = VersionInfo.parse(last_prerelease)
    last_pre_v_finalized = last_pre_v.finalize_version()
    # print(last_pre_v_finalized)

    return last_pre_v_finalized.__str__()

def finalize_prerelease(prerelease):

    if "/" in prerelease:
        prerelease = prerelease.split("/")[-1]

    prerelease_v = VersionInfo.parse(prerelease)
    prerelease_v_finalized = prerelease_v.finalize_version()

    return prerelease_v_finalized.__str__()


def main():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-n", "--nightly",
                      dest="nightly", action="store_true",
                      help="Bump nightly version and return it")
    parser.add_option("-b", "--bump",
                      dest="bump", action="store_true",
                      help="Return if there is something to bump")
    parser.add_option("-r", "--release-latest",
                      dest="releaselatest", action="store_true",
                      help="finalize latest prerelease to a release")
    parser.add_option("-p", "--prerelease",
                      dest="prerelease", action="store",
                      help="define prerelease token")
    parser.add_option("-f", "--finalize",
                      dest="finalize", action="store",
                      help="define prerelease token")
    parser.add_option("-v", "--version",
                      dest="version", action="store",
                      help="work with explicit version")
    parser.add_option("-l", "--lastversion",
                      dest="lastversion", action="store",
                      help="work with explicit version")


    (options, args) = parser.parse_args()

    if options.bump:
        last_CI, last_CI_tag = get_last_version("CI")
        last_release, last_release_tag = get_last_version("release")
        bump_type_CI = release_type(get_log_since_tag(last_CI_tag))
        bump_type_release = release_type(get_log_since_tag(last_release_tag))
        if bump_type_CI is None or bump_type_release is None:
            print("skip")

    if options.nightly:
        next_tag_v = calculate_next_nightly()
        print(next_tag_v)
        bump_file_versions(next_tag_v)

    if options.finalize:
        new_release = finalize_prerelease(options.finalize)
        print(new_release)
        bump_file_versions(new_release)

    if options.lastversion:
        last_release, last_release_tag = get_last_version(options.lastversion)
        print(last_release_tag)

    if options.releaselatest:
        new_release = finalize_latest_nightly()
        last_release, last_release_tag = get_last_version("release")

        if VersionInfo.parse(new_release) > VersionInfo.parse(last_release):
            print(new_release)
            bump_file_versions(new_release)
        else:
            print("skip")

    if options.prerelease:
        current_prerelease = VersionInfo.parse(options.prerelease)
        new_prerelease = current_prerelease.bump_prerelease().__str__()
        print(new_prerelease)
        bump_file_versions(new_prerelease)
    
    if options.version:
        bump_file_versions(options.version)
        print(f"Injected version {options.version} into the release")



if __name__ == "__main__":
    main()
