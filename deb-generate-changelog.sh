#!/bin/sh
set -e
# Generate debian changelog from git
PKGNAME=$(sed -n 's/^Package: //p' debian/control)
CHANGELOG_FILE='debian/changelog'

> ${CHANGELOG_FILE}


git tag -l '*' | sort -V | while read TAG; do 
    C="$(git log --pretty=format:'  * %h %s' $PREVTAG..$TAG)"
    (
        echo "$PKGNAME (${TAG#v}) unstable; urgency=low, binary-only=yes"; 
        if [ -z "${C}" ]; then
            echo "  * NOTHING"
        else
            echo "${C}"
        fi
        echo
        git log --pretty='format: -- %aN <%aE>  %aD%n%n' $TAG^..$TAG | head -1
    ) | cat - ${CHANGELOG_FILE} | sponge ${CHANGELOG_FILE}
    PREVTAG=$TAG
done


HEAD_TAG=$(git tag -l '*' | sort -V | tail -1)
HEAD_VER=$(git describe --tags | sed 's/-/+/g')
echo head tag: ${HEAD}
HEAD_COMMIT=$(git log --pretty=format:'  * %h %s' ${HEAD_TAG}..HEAD)
if ! [ -z "${HEAD_COMMIT}" ]; then
    (
        echo "$PKGNAME (${HEAD_VER#v}) unstable; urgency=low, binary-only=yes"
        echo "${HEAD_COMMIT}"
        git log --pretty='format: -- %aN <%aE>  %aD%n%n' ${HEAD_TAG}^..HEAD | head -1
    ) | cat - ${CHANGELOG_FILE} | sponge ${CHANGELOG_FILE}
fi
