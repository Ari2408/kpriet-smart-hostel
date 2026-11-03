import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/staff_provider.dart';

class AddStudentScreen extends StatefulWidget {
  const AddStudentScreen({super.key});

  @override
  State<AddStudentScreen> createState() => _AddStudentScreenState();
}

class _AddStudentScreenState extends State<AddStudentScreen> {
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _regNoController = TextEditingController();
  final _roomController = TextEditingController();
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;

  String _selectedDepartment = "Computer Science & Engineering";
  int _selectedYear = 1;
  String _selectedHostelBlock = "Emerald Block";

  final List<String> _departments = [
    "Computer Science & Engineering",
    "Artificial Intelligence & Data Science",
    "Electronics & Communication Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical & Electronics Engineering",
    "Biomedical Engineering",
    "Information Technology",
  ];

  final List<String> _hostelBlocks = [
    "Emerald Block",
    "Ruby Block",
    "Diamond Block",
    "Pearl Block",
    "Sapphire Block",
  ];

  File? _selectedPhoto;
  String? _photoBase64;
  final ImagePicker _picker = ImagePicker();

  @override
  void dispose() {
    _nameController.dispose();
    _regNoController.dispose();
    _roomController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _takePhoto(ImageSource source) async {
    try {
      final XFile? file = await _picker.pickImage(
        source: source,
        maxWidth: 720,
        maxHeight: 720,
        imageQuality: 90,
      );

      if (file != null) {
        final bytes = await file.readAsBytes();
        setState(() {
          _selectedPhoto = File(file.path);
          _photoBase64 = base64Encode(bytes);
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error picking image: ${e.toString()}")),
      );
    }
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return "Initial password is required";
    }
    if (value.length < 8) {
      return "Password must be at least 8 characters long";
    }
    if (!RegExp(r'[A-Za-z]').hasMatch(value) || !RegExp(r'\d').hasMatch(value)) {
      return "Must contain letters and numbers";
    }
    return null;
  }

  void _submit() async {
    if (!_formKey.currentState!.validate()) return;

    if (_photoBase64 == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("A clear student photograph is required to generate the facial biometric profile."),
          backgroundColor: AppColors.absentRed,
        ),
      );
      return;
    }

    final staffProv = context.read<StaffProvider>();
    final regNo = _regNoController.text.trim();
    final studentName = _nameController.text.trim();
    final pwd = _passwordController.text;

    final success = await staffProv.addStudent(
      registerNumber: regNo,
      name: studentName,
      email: _emailController.text.trim().isNotEmpty ? _emailController.text.trim() : null,
      password: pwd,
      confirmPassword: _confirmPasswordController.text,
      department: _selectedDepartment,
      academicYear: _selectedYear,
      hostelBlock: _selectedHostelBlock,
      roomNumber: _roomController.text.trim(),
      phoneNumber: _phoneController.text.trim().isNotEmpty ? _phoneController.text.trim() : null,
      profileImageBase64: _photoBase64!,
    );

    if (!mounted) return;

    if (success) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => AlertDialog(
          icon: const Icon(Icons.check_circle_rounded, color: AppColors.presentGreen, size: 52),
          title: const Text(
            "Student account created successfully.",
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
            textAlign: TextAlign.center,
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.surfaceMuted,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.dividerColor),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text("Student: $studentName", style: const TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Text("Register Number: $regNo", style: const TextStyle(color: AppColors.primaryNavy, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 4),
                    const Text("Role: Student", style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              const Text(
                "Confirmation: Initial password has been configured securely using bcrypt hashing. The student can now log in using their Register Number and this password.",
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary, height: 1.4),
              ),
            ],
          ),
          actions: [
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryNavy,
                minimumSize: const Size.fromHeight(44),
              ),
              onPressed: () {
                Navigator.pop(ctx); // Close dialog
                Navigator.pop(context); // Return to student list
              },
              child: const Text("Done"),
            ),
          ],
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(staffProv.errorMessage ?? "Registration failed"),
          backgroundColor: AppColors.absentRed,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final staffProv = context.watch<StaffProvider>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text("Add Student"),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Photo Upload Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      const Text(
                        "STUDENT BIOMETRIC PHOTOGRAPH",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        "Used by facial recognition service to generate 128D facial profile embedding.",
                        style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      Center(
                        child: Container(
                          width: 130,
                          height: 150,
                          decoration: BoxDecoration(
                            color: AppColors.surfaceMuted,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: _selectedPhoto != null
                                  ? AppColors.presentGreen
                                  : AppColors.dividerColor,
                              width: 2,
                            ),
                          ),
                          child: _selectedPhoto != null
                              ? ClipRRect(
                                  borderRadius: BorderRadius.circular(14),
                                  child: Image.file(_selectedPhoto!, fit: BoxFit.cover),
                                )
                              : const Icon(
                                  Icons.add_a_photo_rounded,
                                  size: 44,
                                  color: AppColors.textMuted,
                                ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          OutlinedButton.icon(
                            icon: const Icon(Icons.camera_alt_rounded, size: 18),
                            label: const Text("Capture"),
                            onPressed: () => _takePhoto(ImageSource.camera),
                          ),
                          const SizedBox(width: 12),
                          OutlinedButton.icon(
                            icon: const Icon(Icons.photo_library_rounded, size: 18),
                            label: const Text("Gallery"),
                            onPressed: () => _takePhoto(ImageSource.gallery),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 18),

              // Student Details Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "STUDENT INFORMATION",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _nameController,
                        decoration: const InputDecoration(
                          labelText: "Student Name *",
                          prefixIcon: Icon(Icons.person_outline),
                        ),
                        validator: (v) => (v == null || v.trim().isEmpty) ? "Student name is required" : null,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _regNoController,
                        decoration: const InputDecoration(
                          labelText: "Register Number *",
                          hintText: "e.g. 711321104010",
                          prefixIcon: Icon(Icons.badge_outlined),
                        ),
                        validator: (v) => (v == null || v.trim().isEmpty) ? "Register number is required" : null,
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<String>(
                        value: _selectedDepartment,
                        decoration: const InputDecoration(labelText: "Department"),
                        items: _departments.map((d) => DropdownMenuItem(value: d, child: Text(d, style: const TextStyle(fontSize: 13)))).toList(),
                        onChanged: (v) => setState(() => _selectedDepartment = v!),
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<int>(
                        value: _selectedYear,
                        decoration: const InputDecoration(labelText: "Academic Year"),
                        items: [1, 2, 3, 4].map((y) => DropdownMenuItem(value: y, child: Text("Year $y"))).toList(),
                        onChanged: (v) => setState(() => _selectedYear = v!),
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<String>(
                        value: _selectedHostelBlock,
                        decoration: const InputDecoration(labelText: "Hostel Block"),
                        items: _hostelBlocks.map((b) => DropdownMenuItem(value: b, child: Text(b))).toList(),
                        onChanged: (v) => setState(() => _selectedHostelBlock = v!),
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _roomController,
                        decoration: const InputDecoration(
                          labelText: "Room Number *",
                          hintText: "e.g. B-204",
                          prefixIcon: Icon(Icons.meeting_room_outlined),
                        ),
                        validator: (v) => (v == null || v.trim().isEmpty) ? "Room number is required" : null,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _phoneController,
                        decoration: const InputDecoration(
                          labelText: "Contact Number",
                          hintText: "+91 98765 43210",
                          prefixIcon: Icon(Icons.phone_outlined),
                        ),
                        keyboardType: TextInputType.phone,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _emailController,
                        decoration: const InputDecoration(
                          labelText: "Student Email (optional)",
                          hintText: "student@kpriet.ac.in",
                          prefixIcon: Icon(Icons.email_outlined),
                        ),
                        keyboardType: TextInputType.emailAddress,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 18),

              // Warden-Controlled Password Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "WARDEN-CONTROLLED INITIAL PASSWORD",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        "Create the student's initial login password. It will be securely hashed with bcrypt.",
                        style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: _obscurePassword,
                        decoration: InputDecoration(
                          labelText: "Create Password *",
                          hintText: "Min 8 chars, letters & numbers",
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            icon: Icon(_obscurePassword ? Icons.visibility_off : Icons.visibility),
                            onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                          ),
                        ),
                        validator: _validatePassword,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _confirmPasswordController,
                        obscureText: _obscureConfirmPassword,
                        decoration: InputDecoration(
                          labelText: "Confirm Password *",
                          prefixIcon: const Icon(Icons.lock_reset_rounded),
                          suffixIcon: IconButton(
                            icon: Icon(_obscureConfirmPassword ? Icons.visibility_off : Icons.visibility),
                            onPressed: () => setState(() => _obscureConfirmPassword = !_obscureConfirmPassword),
                          ),
                        ),
                        validator: (val) {
                          if (val == null || val.isEmpty) return "Please confirm password";
                          if (val != _passwordController.text) return "Passwords do not match";
                          return null;
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primaryNavy,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                onPressed: staffProv.isLoading ? null : _submit,
                child: staffProv.isLoading
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                      )
                    : const Text(
                        "Register Student",
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
