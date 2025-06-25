// script.js

// -------------------------------------
// Simple Markdown Parser
// -------------------------------------
/**
 * parseMarkdown transforms basic Markdown syntax in a text string into HTML.
 */
function parseMarkdown(text) {
  // Convert Markdown **bold** syntax to <strong> HTML tags
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Convert Markdown *italic* syntax to <em> HTML tags
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Convert Markdown headings (# at line start) to <h3> elements using global multiline flag
  text = text.replace(/^#\s*(.+)$/gm, '<h3>$1</h3>');
  // Convert newline characters to <br> tags for HTML line breaks
  return text.replace(/\n/g, '<br>');
}

// -------------------------------------
// Render existing comments as Markdown → HTML
// -------------------------------------
/**
 * On DOMContentLoaded, find all elements with class .comment-body and replace text with parsed HTML.
 */
window.addEventListener('DOMContentLoaded', () => {
  // Select each span containing raw Markdown text
  document.querySelectorAll('.comment-body').forEach(span => {
    // Replace span’s inner HTML with the result of parseMarkdown on its text content
    span.innerHTML = parseMarkdown(span.textContent);
  });
});

// -------------------------------------
// Tag Filtering Feature
// -------------------------------------
/**
 * filterByTag shows or hides feedback boxes based on a given tag.
 */
function filterByTag(tag) {
  // Iterate over all feedback items
  document.querySelectorAll('.feedback-box').forEach(div => {
    // Read the data-tags attribute, lowercase it, split by commas, and trim each tag
    const tagList = (div.dataset.tags || '')
                       .toLowerCase()
                       .split(',')
                       .map(t => t.trim());
    // Display the div if its tag list contains the filter tag; otherwise hide it
    div.style.display = tagList.includes(tag) ? 'block' : 'none';
  });
}

// -------------------------------------
// PDF Export Utility
// -------------------------------------
/**
 * exportPDF opens a new browser tab/window to download the PDF for a specific feedback ID.
 */
function exportPDF(fid) {
  // Open the /export_feedback/<fid> endpoint in a new tab to trigger download
  window.open(`/export_feedback/${fid}`, '_blank');
}
