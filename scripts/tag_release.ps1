param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$Summary
)
$tag = "v$Version"
git tag -a $tag -m "Release ${tag}: $Summary"
if ($LASTEXITCODE -eq 0) {
    git push origin $tag
    Write-Host "Tag $tag pushed successfully." -ForegroundColor Green
} else {
    Write-Host "Tagging failed. Check if $tag already exists." -ForegroundColor Red
}
