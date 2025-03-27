/**
 * Main JavaScript for School Management System
 */

// DOM Ready function
document.addEventListener("DOMContentLoaded", () => {
  // Initialize tooltips
  initTooltips()

  // Initialize sidebar active link
  setActiveSidebarLink()

  // Initialize alert dismissal
  initAlertDismissal()

  // Initialize responsive tables
  initResponsiveTables()

  // Initialize smooth scrolling
  initSmoothScroll()

  // Initialize touch events
  handleTouchEvents()
})

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  tooltipTriggerList.map((tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl))
}

/**
 * Set active sidebar link based on current URL
 */
function setActiveSidebarLink() {
  const currentLocation = window.location.pathname
  const sidebarLinks = document.querySelectorAll(".sidebar-link")

  sidebarLinks.forEach((link) => {
    const href = link.getAttribute("href")
    if (href && currentLocation.includes(href) && href !== "#") {
      link.classList.add("active")
    }
  })
}

/**
 * Initialize alert dismissal after timeout
 */
function initAlertDismissal() {
  const alerts = document.querySelectorAll(".alert:not(.alert-permanent)")
  alerts.forEach((alert) => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert)
      bsAlert.close()
    }, 5000) // Auto dismiss after 5 seconds
  })
}

/**
 * Initialize responsive tables
 */
function initResponsiveTables() {
  const tables = document.querySelectorAll(".table-responsive-card")

  tables.forEach((table) => {
    const headerCells = table.querySelectorAll("thead th")
    const dataCells = table.querySelectorAll("tbody td")

    // Add data-label attribute to each cell based on the corresponding header
    dataCells.forEach((cell, index) => {
      const headerIndex = index % headerCells.length
      const headerText = headerCells[headerIndex].textContent.trim()
      cell.setAttribute("data-label", headerText)
    })
  })
}

/**
 * Initialize smooth scrolling for anchor links
 */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]:not([data-bs-toggle])').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault()

      const targetId = this.getAttribute("href")
      if (targetId === "#") return

      const targetElement = document.querySelector(targetId)

      if (targetElement) {
        // Close sidebar on mobile if open
        if (window.innerWidth < 992 && document.body.classList.contains("sidebar-open")) {
          document.body.classList.remove("sidebar-open")
          const toggle = document.getElementById("sidebarToggle")
          if (toggle) {
            const icon = toggle.querySelector("i")
            icon.classList.remove("fa-times")
            icon.classList.add("fa-bars")
          }
        }

        // Scroll to target with offset for fixed header
        const yOffset = -20
        const y = targetElement.getBoundingClientRect().top + window.pageYOffset + yOffset

        window.scrollTo({ top: y, behavior: "smooth" })
      }
    })
  })
}

/**
 * Format date to readable string
 * @param {Date} date - Date object to format
 * @param {boolean} includeTime - Whether to include time
 * @returns {string} Formatted date string
 */
function formatDate(date, includeTime = false) {
  if (!date) return ""

  const options = {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }

  if (includeTime) {
    options.hour = "2-digit"
    options.minute = "2-digit"
  }

  return new Date(date).toLocaleDateString(undefined, options)
}

/**
 * Calculate duration between two dates in minutes
 * @param {Date} startDate - Start date
 * @param {Date} endDate - End date
 * @returns {number} Duration in minutes
 */
function calculateDuration(startDate, endDate) {
  if (!startDate || !endDate) return 0

  const start = new Date(startDate)
  const end = new Date(endDate)
  const durationMs = end - start

  return Math.round(durationMs / (1000 * 60))
}

/**
 * Initialize webcam for biometric verification
 * @param {string} videoElementId - ID of video element
 * @returns {Promise<MediaStream>} Media stream
 */
async function initWebcam(videoElementId) {
  try {
    const videoElement = document.getElementById(videoElementId)
    if (!videoElement) return null

    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    })
    videoElement.srcObject = stream
    return stream
  } catch (err) {
    console.error("Error accessing webcam:", err)
    alert("Error accessing webcam. Please make sure your camera is connected and permissions are granted.")
    return null
  }
}

/**
 * Capture image from webcam
 * @param {string} videoElementId - ID of video element
 * @param {string} canvasElementId - ID of canvas element
 * @returns {string} Base64 image data
 */
function captureImage(videoElementId, canvasElementId) {
  const video = document.getElementById(videoElementId)
  const canvas = document.getElementById(canvasElementId)
  if (!video || !canvas) return null

  const context = canvas.getContext("2d")
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  context.drawImage(video, 0, 0, canvas.width, canvas.height)

  return canvas.toDataURL("image/png")
}

/**
 * Stop webcam stream
 * @param {MediaStream} stream - Media stream to stop
 */
function stopWebcam(stream) {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
  }
}

/**
 * Handle touch events for mobile devices
 */
function handleTouchEvents() {
  // Add touch support for dropdowns
  document.querySelectorAll(".dropdown-toggle").forEach((item) => {
    item.addEventListener("touchstart", function (e) {
      e.preventDefault()
      const dropdown = bootstrap.Dropdown.getOrCreateInstance(this)
      dropdown.toggle()
    })
  })

  // Add touch support for tooltips
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((item) => {
    item.addEventListener("touchstart", function (e) {
      e.preventDefault()
      const tooltip = bootstrap.Tooltip.getOrCreateInstance(this)
      tooltip.toggle()
    })
  })
}

