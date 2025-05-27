
git tag -a v8.4.0-alpha.11 -m "chore(release): v8.4.0-alpha.11"
git push origin v8.4.0-alpha.11

git tag -a v8.4.0-alpha.12 -m "chore(release): v8.4.0-alpha.12"
git push origin v8.4.0-alpha.12

git tag -a v8.4.0-alpha.13 -m "chore(release): v8.4.0-alpha.13"
git push origin v8.4.0-alpha.13

######################################################
# 8.4.0
######################################################

git switch chore_release-8.4.0 && git pull
# look at the commit history
git log --oneline -n 20

# check out the release branch
git switch release && git pull
# look at the commit history
git log --oneline -n 20

# now do the merge
# the PR must be approved
git merge --ff-only chore_release-8.4.0
git push origin release

# https://github.com/Opentrons/opentrons/pull/17882
# Now the PR will show merged

# Now we tag the release branch

git tag -a v8.4.0 -m "chore(release): v8.4.0"
git push origin v8.4.0



git checkout main && git pull
git checkout chore_release-8.4.0 && git pull
git checkout -b chore_release-8.4.0_to_main_for_8.4.0
git merge merge main
git push
