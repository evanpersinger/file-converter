const MB = 1024 * 1024

// MAX_CONVERT_BYTES and MAX_COMBINE_BYTES in server.py, repeated so an oversize file is
// reported before it uploads. The server still refuses anything over them. The batch limit
// is the UI's alone, since the server only ever sees one file per request.
const MAX_CONVERT_BYTES = 100 * MB
const MAX_BATCH_BYTES = 300 * MB
const MAX_COMBINE_BYTES = 500 * MB

const totalSize = (files: File[]) => files.reduce((sum, file) => sum + file.size, 0)

/** Whether the server would refuse this file for a conversion, or for the type check. */
export const overConvertLimit = (file: File) => file.size > MAX_CONVERT_BYTES

/** What to tell the user when these files are over the limits for converting, else null. */
export function convertLimitMessage(files: File[]): string | null {
  const tooBig = files.filter(overConvertLimit)
  if (tooBig.length > 0) {
    const names = tooBig.map((file) => file.name).join(', ')
    const verb = tooBig.length === 1 ? 'is' : 'are'
    return `${names} ${verb} over the ${MAX_CONVERT_BYTES / MB} MB limit for converting a file. Remove ${tooBig.length === 1 ? 'it' : 'them'} to continue.`
  }
  if (totalSize(files) > MAX_BATCH_BYTES) {
    return `These files add up to more than ${MAX_BATCH_BYTES / MB} MB. Convert them in smaller batches.`
  }
  return null
}

/** The same for combining, which takes more because it only merges the files. */
export function combineLimitMessage(files: File[]): string | null {
  if (totalSize(files) > MAX_COMBINE_BYTES) {
    return `These files add up to more than the ${MAX_COMBINE_BYTES / MB} MB limit for combining.`
  }
  return null
}
