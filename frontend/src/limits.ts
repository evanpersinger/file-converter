import { extensionOf } from './api'

const MB = 1024 * 1024
const GB = 1024 * MB

// MAX_CONVERT_BYTES, MAX_VIDEO_BYTES and MAX_COMBINE_BYTES in server.py, repeated so an
// oversize file is reported before it uploads. The server still refuses anything over them.
// The batch limit is the UI's alone, since the server only ever sees one file per request.
const MAX_CONVERT_BYTES = 100 * MB
const MAX_VIDEO_BYTES = 5 * GB
const MAX_BATCH_BYTES = 300 * MB
const MAX_COMBINE_BYTES = 500 * MB

// The types the server gives the bigger video limit.
const VIDEO_EXTS = ['.mp4']

const isVideo = (file: File) => VIDEO_EXTS.includes(extensionOf(file.name))
const convertLimit = (file: File) => (isVideo(file) ? MAX_VIDEO_BYTES : MAX_CONVERT_BYTES)

// A limit as it reads in a message: whole gigabytes as GB, anything else as MB.
const sizeLabel = (bytes: number) =>
  bytes >= GB && bytes % GB === 0 ? `${bytes / GB} GB` : `${bytes / MB} MB`

const totalSize = (files: File[]) => files.reduce((sum, file) => sum + file.size, 0)

/** Whether the server would refuse this file for the type check, which takes the plain convert limit. */
export const overDetectLimit = (file: File) => file.size > MAX_CONVERT_BYTES

/** What to tell the user when these files are over the limits for converting, else null. */
export function convertLimitMessage(files: File[]): string | null {
  const tooBig = files.filter((file) => file.size > convertLimit(file))
  if (tooBig.length > 0) {
    const names = tooBig.map((file) => file.name).join(', ')
    const verb = tooBig.length === 1 ? 'is' : 'are'
    // Converting needs one format for every file, so they all share the first one's limit.
    return `${names} ${verb} over the ${sizeLabel(convertLimit(tooBig[0]))} limit for converting a file. Remove ${tooBig.length === 1 ? 'it' : 'them'} to continue.`
  }
  // Videos are left out of the total, each one is held to its own limit above.
  if (totalSize(files.filter((file) => !isVideo(file))) > MAX_BATCH_BYTES) {
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
