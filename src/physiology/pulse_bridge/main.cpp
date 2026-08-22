// Engineering-only Pulse SDK bridge probe for Nexora VPE S0.
// It is not clinical decision support, diagnosis, or treatment advice.
#include "pulse/engine/PulseEngine.h"
#include "pulse/cdm/patient/actions/SEHemorrhage.h"
#include "pulse/cdm/properties/SEScalarFrequency.h"
#include "pulse/cdm/properties/SEScalarPressure.h"
#include "pulse/cdm/properties/SEScalarTime.h"
#include "pulse/cdm/properties/SEScalarVolume.h"
#include "pulse/cdm/properties/SEScalarVolumePerTime.h"
#include "pulse/cdm/system/physiology/SEBloodChemistrySystem.h"
#include "pulse/cdm/system/physiology/SECardiovascularSystem.h"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

namespace {

struct Telemetry {
  double time_s;
  double heart_rate_bpm;
  double map_mmhg;
  double blood_volume_ml;
  double total_hemorrhaged_volume_ml;
  double oxygen_saturation;
};

Telemetry Capture(const PhysiologyEngine& engine) {
  const auto* cardiovascular = engine.GetCardiovascularSystem();
  const auto* chemistry = engine.GetBloodChemistrySystem();
  return {
    engine.GetSimulationTime(TimeUnit::s),
    cardiovascular->GetHeartRate(FrequencyUnit::Per_min),
    cardiovascular->GetMeanArterialPressure(PressureUnit::mmHg),
    cardiovascular->GetBloodVolume(VolumeUnit::mL),
    cardiovascular->GetTotalHemorrhagedVolume(VolumeUnit::mL),
    chemistry->GetOxygenSaturation(),
  };
}

bool Advance(PhysiologyEngine& engine, double duration_s) {
  return engine.AdvanceModelTime(duration_s, TimeUnit::s);
}

void WriteTelemetry(std::ostream& stream, const char* name, const Telemetry& t, bool trailing_comma) {
  stream << "  \"" << name << "\": {\n"
         << "    \"time_s\": " << t.time_s << ",\n"
         << "    \"heart_rate_bpm\": " << t.heart_rate_bpm << ",\n"
         << "    \"mean_arterial_pressure_mmhg\": " << t.map_mmhg << ",\n"
         << "    \"blood_volume_ml\": " << t.blood_volume_ml << ",\n"
         << "    \"total_hemorrhaged_volume_ml\": " << t.total_hemorrhaged_volume_ml << ",\n"
         << "    \"oxygen_saturation\": " << t.oxygen_saturation << "\n"
         << "  }" << (trailing_comma ? "," : "") << "\n";
}

}  // namespace

int main(int argc, char* argv[]) {
  const std::string state_file = argc > 1 ? argv[1] : "./states/StandardMale@0s.json";
  const std::string output_file = argc > 2 ? argv[2] : "./test_results/nexora_pulse_bridge.json";
  const std::string snapshot_file = argc > 3 ? argv[3] : "./test_results/nexora_pulse_bridge_state.json";

  std::filesystem::create_directories(std::filesystem::path(output_file).parent_path());
  std::filesystem::create_directories(std::filesystem::path(snapshot_file).parent_path());

  auto engine = CreatePulseEngine();
  engine->GetLogger()->LogToConsole(false);
  if (!engine->SerializeFromFile(state_file)) {
    std::cerr << "Failed to load Pulse state: " << state_file << "\n";
    return 2;
  }

  const auto baseline = Capture(*engine);

  SEHemorrhage hemorrhage;
  hemorrhage.SetCompartment(eHemorrhage_Compartment::Spleen);
  hemorrhage.SetType(eHemorrhage_Type::Internal);
  hemorrhage.GetFlowRate().SetValue(60.0, VolumePerTimeUnit::mL_Per_min);
  if (!engine->ProcessAction(hemorrhage) || !Advance(*engine, 120.0)) {
    std::cerr << "Failed to apply or advance internal splenic hemorrhage\n";
    return 3;
  }
  const auto before_snapshot = Capture(*engine);

  if (!engine->SerializeToFile(snapshot_file)) {
    std::cerr << "Failed to save Pulse state: " << snapshot_file << "\n";
    return 4;
  }
  if (!Advance(*engine, 60.0)) {
    std::cerr << "Failed to advance original trajectory\n";
    return 5;
  }
  const auto original_continued = Capture(*engine);

  auto restored = CreatePulseEngine();
  restored->GetLogger()->LogToConsole(false);
  if (!restored->SerializeFromFile(snapshot_file) || !Advance(*restored, 60.0)) {
    std::cerr << "Failed to restore and advance Pulse state\n";
    return 6;
  }
  const auto restored_continued = Capture(*restored);

  std::ofstream output(output_file);
  if (!output) {
    std::cerr << "Failed to open output: " << output_file << "\n";
    return 7;
  }
  output << std::fixed << std::setprecision(6);
  output << "{\n"
         << "  \"purpose\": \"Engineering-only Pulse SDK bridge probe; not clinical advice.\",\n"
         << "  \"pulse_version\": \"" << PulseBuildInformation::Version() << "\",\n"
         << "  \"pulse_hash\": \"" << PulseBuildInformation::Hash() << "\",\n"
         << "  \"state_file\": \"" << state_file << "\",\n"
         << "  \"snapshot_file\": \"" << snapshot_file << "\",\n";
  WriteTelemetry(output, "baseline", baseline, true);
  WriteTelemetry(output, "before_snapshot", before_snapshot, true);
  WriteTelemetry(output, "original_continued", original_continued, true);
  WriteTelemetry(output, "restored_continued", restored_continued, false);
  output << "}\n";

  std::cout << "Wrote " << output_file << "\n";
  return 0;
}
