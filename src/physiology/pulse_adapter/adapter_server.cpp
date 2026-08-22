// Nexora PulseAdapter server: engineering-only simulation infrastructure.
// It is not clinical decision support, diagnosis, or treatment advice.
#include "pulse/engine/PulseEngine.h"
#include "pulse/cdm/patient/actions/SEHemorrhage.h"
#include "pulse/cdm/patient/actions/SESubstanceCompoundInfusion.h"
#include "pulse/cdm/properties/SEScalarFrequency.h"
#include "pulse/cdm/properties/SEScalarPressure.h"
#include "pulse/cdm/properties/SEScalarTime.h"
#include "pulse/cdm/properties/SEScalarVolume.h"
#include "pulse/cdm/properties/SEScalarVolumePerTime.h"
#include "pulse/cdm/substance/SESubstanceCompound.h"
#include "pulse/cdm/substance/SESubstanceManager.h"
#include "pulse/cdm/system/physiology/SEBloodChemistrySystem.h"
#include "pulse/cdm/system/physiology/SECardiovascularSystem.h"

#include <cmath>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::vector<std::string> SplitTabs(const std::string& line) {
  std::vector<std::string> fields;
  std::stringstream input(line);
  std::string field;
  while (std::getline(input, field, '\t')) {
    fields.push_back(field);
  }
  return fields;
}

std::string SingleLine(std::string text) {
  for (char& character : text) {
    if (character == '\t' || character == '\n' || character == '\r') {
      character = ' ';
    }
  }
  return text;
}

void Ok(const std::string& payload = "") {
  std::cout << "OK";
  if (!payload.empty()) {
    std::cout << '\t' << payload;
  }
  std::cout << '\n' << std::flush;
}

void Error(const std::string& message) {
  std::cout << "ERR\t" << SingleLine(message) << '\n' << std::flush;
}

double ParsePositiveDouble(const std::string& raw, const std::string& name) {
  std::size_t consumed = 0;
  const double value = std::stod(raw, &consumed);
  if (consumed != raw.size() || !std::isfinite(value) || value <= 0.0) {
    throw std::runtime_error(name + " must be a positive finite number");
  }
  return value;
}

class AdapterServer {
 public:
  void Run() {
    std::string line;
    while (std::getline(std::cin, line)) {
      if (line.empty()) {
        Error("empty command");
        continue;
      }
      try {
        const auto fields = SplitTabs(line);
        if (fields.empty()) {
          Error("empty command");
          continue;
        }
        if (fields[0] == "VERSION") {
          RequireArity(fields, 1);
          Ok(PulseBuildInformation::Version() + "\t" + PulseBuildInformation::Hash());
        } else if (fields[0] == "BOOTSTRAP") {
          RequireArity(fields, 4);
          Bootstrap(fields[1], fields[2], ParsePositiveDouble(fields[3], "hemorrhage flow"));
          Ok(FormatNumber(engine_->GetSimulationTime(TimeUnit::s)));
        } else if (fields[0] == "ADVANCE") {
          RequireArity(fields, 2);
          RequireEngine();
          const double duration_s = ParsePositiveDouble(fields[1], "duration");
          if (!engine_->AdvanceModelTime(duration_s, TimeUnit::s)) {
            throw std::runtime_error("Pulse could not advance the requested simulation duration");
          }
          Ok(FormatNumber(engine_->GetSimulationTime(TimeUnit::s)));
        } else if (fields[0] == "APPLY") {
          RequireArity(fields, 4);
          RequireEngine();
          ApplyInfusion(fields[1], ParsePositiveDouble(fields[2], "volume"), ParsePositiveDouble(fields[3], "rate"));
          Ok(FormatNumber(engine_->GetSimulationTime(TimeUnit::s)));
        } else if (fields[0] == "TELEMETRY") {
          RequireEngine();
          EmitTelemetry(fields);
        } else if (fields[0] == "TIME") {
          RequireArity(fields, 1);
          RequireEngine();
          Ok(FormatNumber(engine_->GetSimulationTime(TimeUnit::s)));
        } else if (fields[0] == "SAVE") {
          RequireArity(fields, 2);
          RequireEngine();
          const std::filesystem::path path(fields[1]);
          if (!path.parent_path().empty()) {
            std::filesystem::create_directories(path.parent_path());
          }
          if (!engine_->SerializeToFile(path.string())) {
            throw std::runtime_error("Pulse could not serialize the requested state");
          }
          Ok(FormatNumber(engine_->GetSimulationTime(TimeUnit::s)));
        } else if (fields[0] == "RESTORE") {
          RequireArity(fields, 2);
          Restore(fields[1]);
          Ok(FormatNumber(engine_->GetSimulationTime(TimeUnit::s)));
        } else if (fields[0] == "QUIT") {
          RequireArity(fields, 1);
          Ok();
          return;
        } else {
          throw std::runtime_error("unsupported command");
        }
      } catch (const std::exception& exception) {
        Error(exception.what());
      }
    }
  }

 private:
  std::unique_ptr<PhysiologyEngine> engine_;

  static void RequireArity(const std::vector<std::string>& fields, std::size_t expected) {
    if (fields.size() != expected) {
      throw std::runtime_error("unexpected command field count");
    }
  }

  void RequireEngine() const {
    if (!engine_) {
      throw std::runtime_error("adapter has not been bootstrapped or restored");
    }
  }

  static std::string FormatNumber(double value) {
    std::ostringstream output;
    output << std::setprecision(17) << value;
    return output.str();
  }

  void NewEngine() {
    engine_ = CreatePulseEngine();
    engine_->GetLogger()->LogToConsole(false);
  }

  void Bootstrap(const std::string& state_file, const std::string& compartment, double flow_ml_min) {
    if (engine_) {
      throw std::runtime_error("adapter is already initialized");
    }
    if (compartment != "Spleen") {
      throw std::runtime_error("S0 adapter only permits the Spleen hemorrhage compartment");
    }
    NewEngine();
    if (!engine_->SerializeFromFile(state_file)) {
      engine_.reset();
      throw std::runtime_error("Pulse could not load the requested initial state");
    }
    SEHemorrhage hemorrhage;
    hemorrhage.SetCompartment(eHemorrhage_Compartment::Spleen);
    hemorrhage.SetType(eHemorrhage_Type::Internal);
    hemorrhage.GetFlowRate().SetValue(flow_ml_min, VolumePerTimeUnit::mL_Per_min);
    if (!engine_->ProcessAction(hemorrhage)) {
      engine_.reset();
      throw std::runtime_error("Pulse could not apply the existing internal splenic hemorrhage");
    }
  }

  void Restore(const std::string& state_file) {
    NewEngine();
    if (!engine_->SerializeFromFile(state_file)) {
      engine_.reset();
      throw std::runtime_error("Pulse could not restore the requested state");
    }
  }

  void ApplyInfusion(const std::string& compound_name, double volume_ml, double rate_ml_min) {
    if (compound_name != "Saline" && compound_name != "PackedRBC") {
      throw std::runtime_error("S0 adapter received an unsupported compound");
    }
    const SESubstanceCompound* compound = engine_->GetSubstanceManager().GetCompound(compound_name);
    if (compound == nullptr) {
      throw std::runtime_error("Pulse SDK is missing the requested compound");
    }
    SESubstanceCompoundInfusion infusion(*compound);
    infusion.GetBagVolume().SetValue(volume_ml, VolumeUnit::mL);
    infusion.GetRate().SetValue(rate_ml_min, VolumePerTimeUnit::mL_Per_min);
    if (!engine_->ProcessAction(infusion)) {
      throw std::runtime_error("Pulse could not apply the requested constrained infusion");
    }
  }

  double TelemetryValue(const std::string& key) const {
    const auto* cardiovascular = engine_->GetCardiovascularSystem();
    const auto* chemistry = engine_->GetBloodChemistrySystem();
    if (key == "heart_rate_bpm") {
      return cardiovascular->GetHeartRate(FrequencyUnit::Per_min);
    }
    if (key == "mean_arterial_pressure_mmhg") {
      return cardiovascular->GetMeanArterialPressure(PressureUnit::mmHg);
    }
    if (key == "blood_volume_ml") {
      return cardiovascular->GetBloodVolume(VolumeUnit::mL);
    }
    if (key == "total_hemorrhaged_volume_ml") {
      return cardiovascular->GetTotalHemorrhagedVolume(VolumeUnit::mL);
    }
    if (key == "oxygen_saturation") {
      return chemistry->GetOxygenSaturation();
    }
    throw std::runtime_error("unsupported telemetry key");
  }

  void EmitTelemetry(const std::vector<std::string>& fields) const {
    if (fields.size() < 2) {
      throw std::runtime_error("telemetry requires at least one requested key");
    }
    std::ostringstream output;
    output << FormatNumber(engine_->GetSimulationTime(TimeUnit::s));
    for (std::size_t index = 1; index < fields.size(); ++index) {
      output << '\t' << fields[index] << '=' << FormatNumber(TelemetryValue(fields[index]));
    }
    Ok(output.str());
  }
};

}  // namespace

int main() {
  AdapterServer server;
  server.Run();
  return 0;
}
