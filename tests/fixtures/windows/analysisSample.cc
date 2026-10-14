#include <cstdio>
#include <cstdlib>

// Owned, compilable sample for real decompilation and call-graph verification.
extern "C" __declspec(dllexport) __declspec(noinline)
int rea_score(int level, int completed) {
  return level * 10 + (completed ? 25 : 0);
}

extern "C" __declspec(dllexport) __declspec(noinline)
const char* rea_label(int score) {
  return score >= 50 ? "REA_WINDOWS_READY" : "REA_WINDOWS_REVIEW";
}

int main(int argc, char** argv) {
  const int level = argc > 1 ? std::atoi(argv[1]) : 3;
  const int score = rea_score(level, 1);
  std::printf("%s score=%d\n", rea_label(score), score);
  return 0;
}
