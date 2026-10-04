import { describe, expect, it } from 'vitest'
import { shuffleStudyOptions } from '@/pages/student/studyOptions'

describe('study option presentation', () => {
  const canonical = ['Correct', 'B', 'C', 'D'] as const

  it.each([
    { position: 0, draws: [0.99, 0.99, 0.99] },
    { position: 1, draws: [0.99, 0.99, 0] },
    { position: 2, draws: [0.99, 0, 0.99] },
    { position: 3, draws: [0, 0.99, 0.99] },
  ])('can display the correct option at index $position without mutating stored order', ({ position, draws }) => {
    let draw = 0
    const displayed = shuffleStudyOptions(canonical, () => draws[draw++])
    expect(displayed.indexOf('Correct')).toBe(position)
    expect(displayed).toHaveLength(4)
    expect([...displayed].sort()).toEqual([...canonical].sort())
    expect(canonical).toEqual(['Correct', 'B', 'C', 'D'])
  })
})
