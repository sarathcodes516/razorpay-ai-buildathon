/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Buyer-side production palette
        ink: {
          900: "#0F0F0F", // page background
          800: "#1F1F1F", // card / input surface
          700: "#2a2a2a", // visible light border on cards & dividers
          600: "#3a3a3a", // hover / focus border
          500: "#444444", // tertiary text
          400: "#666666", // secondary text
          300: "#888888", // muted text
          200: "#aaaaaa", // labels
          100: "#cccccc", // primary text on dark
          50:  "#e5e5e5", // brightest text
        },
        // Dark-grey input field surface — distinct from the page background
        // (#0F0F0F) and the card surface (#1F1F1F) so the field reads as a
        // sunken control rather than a flat block.
        field: {
          DEFAULT: "#262626", // input/textarea fill
          hover:   "#2a2a2a", // hover state
          focus:   "#3a3a3a", // focus ring / border
        },
        // Light-gray control surface for primary buttons / inputs
        // that should still pop on the dark page without being pure white.
        surface: {
          50:  "#f5f5f5", // button hover (slightly darker than idle)
          100: "#f0f0f0", // input fill
          200: "#ebebeb", // primary button idle (light gray, not pure white)
          300: "#dcdcdc", // pressed / focus
        },
        // Accent green for primary CTAs
        accent: {
          DEFAULT: "#6CE8AA", // idle
          hover:   "#5BD699", // hover
          active:  "#4AC088", // pressed
        },
      },
    },
  },
  plugins: [],
}
