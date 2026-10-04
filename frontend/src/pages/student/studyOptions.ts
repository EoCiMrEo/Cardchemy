/** Copy and shuffle the displayed choices without changing the server's order. */
export function shuffleStudyOptions(options: readonly string[], random: () => number = Math.random): string[] {
  const displayed = [...options]
  for (let index = displayed.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1))
    const swapped = displayed[index]
    displayed[index] = displayed[swapIndex]
    displayed[swapIndex] = swapped
  }
  return displayed
}
